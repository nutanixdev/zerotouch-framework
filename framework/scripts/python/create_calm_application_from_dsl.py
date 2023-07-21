import json
import os
import uuid
import importlib.util
from pathlib import Path
from typing import Union
from calm.dsl.api import get_api_client
from calm.dsl.builtins import SimpleBlueprint, Ref, VmBlueprint, create_blueprint_payload, get_dsl_metadata_map
from calm.dsl.builtins.models.metadata_payload import get_metadata_class_from_module
from calm.dsl.builtins.models import metadata_payload as global_metadata_payload
from calm.dsl.cli.bps import get_blueprint_class_from_module, create_blueprint, get_app, launch_blueprint_simple
from calm.dsl.config import get_context
from helpers.log_utils import get_logger
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateAppFromDsl(Script):
    def __init__(self, data: dict, **kwargs):
        self.data = data
        super(CreateAppFromDsl, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def compile_blueprint(self, bp_file: Union[str, Path], project: dict):
        """
        There is already a compile_blueprint function in bps. But the problem is, our inputs are fed from an input file
        and these variables have to be populated into calm-dsl file. There are few options
        1. Make calm-dsl file a jinja template with variables -> an option that's not scalable
        2. Get the spec from spec_from_file_location, get source code using spec.loader.get_source. Replace variables
        using string replacement -> isn't flexible and we need to keep track of variables, also potentially
        time-consuming in large DSL files
        3. The third option that we'll use is, inject the variables from input file into module namespace. Problem here
        is we shouldn't have variables already defined in the calm-dsl file as exec_module() takes local namespace
        precedence over injected namespace.
        All have their pros and cons, but 3rd seems like the right approach as of now
        """
        """Returns a module given a user python file (.py)"""
        spec = importlib.util.spec_from_file_location("calm.dsl.bp", bp_file)
        user_module = importlib.util.module_from_spec(spec)

        # Here is where we are modifying non-run time variables like ACCOUNT_NAME, CLUSTER_NAME, SUBNET_NAME,
        # PROJECT_NAME. The variables in dsl-file will be injected by the input file parameters if specified
        for var, val in project.items():
            setattr(user_module, var, val)

        try:
            spec.loader.exec_module(user_module)
        except Exception as exp:
            self.exceptions.append(exp)
            return None

        metadata_payload = self.get_metadata_payload(user_module)
        # Set the global metadata payload
        # This metadata payload is used to check if entities like project exists in metadata and
        # the same is used to create BP
        global_metadata_payload._MetadataPayload = metadata_payload

        UserBlueprint = get_blueprint_class_from_module(user_module)
        if UserBlueprint is None:
            return None

        ContextObj = get_context()
        project_config = ContextObj.get_project_config()

        if isinstance(UserBlueprint, type(SimpleBlueprint)):
            bp_payload = UserBlueprint.make_bp_dict()
            if "project_reference" in metadata_payload:
                bp_payload["metadata"]["project_reference"] = metadata_payload[
                    "project_reference"
                ]
            else:
                project_name = project_config["name"]
                bp_payload["metadata"]["project_reference"] = Ref.Project(project_name)
        else:
            if isinstance(UserBlueprint, type(VmBlueprint)):
                UserBlueprint = UserBlueprint.make_bp_obj()

            UserBlueprintPayload, _ = create_blueprint_payload(
                UserBlueprint, metadata=metadata_payload
            )
            bp_payload = UserBlueprintPayload.get_dict()

            # Adding the display map to client attr
            display_name_map = get_dsl_metadata_map()
            bp_payload["spec"]["resources"]["client_attrs"] = {"None": display_name_map}

            # Note - Install/Uninstall runbooks are not actions in Packages.
            # Remove package actions after compiling.
            cdict = bp_payload["spec"]["resources"]
            for package in cdict["package_definition_list"]:
                if "action_list" in package:
                    del package["action_list"]

        return bp_payload

    def execute(self, **kwargs):
        try:
            client = get_api_client()
            # Get the BPs list
            for bp in self.data["bp_list"]:
                for project in self.data.get("projects", []):
                    bp_uuid = self.create_calm_app(client=client, bp=bp, project=project)

                    if bp_uuid:
                        # Delete the blueprint
                        res, err = client.blueprint.delete(bp_uuid)
                        if err:
                            raise Exception("[{}] - {}".format(err["code"], err["error"]))
        except Exception as e:
            self.exceptions.append(e)

    @staticmethod
    def get_metadata_payload(user_metadata_module):
        """
        returns the metadata payload from the user module
        """
        UserMetadata = get_metadata_class_from_module(user_metadata_module)

        payload = {}
        if UserMetadata:
            payload = UserMetadata.get_dict()
        return payload

    def create_calm_app(self, client, bp: dict, project: dict):
        """
        This function uses calm dsl functions to create calm application.
        We use our modified compile method to compile the BP payload
        """
        bp_file = f"{self.data['project_root']}/{bp['dsl_file']}"
        app_name = f"{bp['app_name']}-{project['PROJECT_NAME']}"

        # Compile blueprint
        bp_payload = self.compile_blueprint(
            bp_file,
            project=project
        )

        if bp_payload is None:
            self.logger.error("User blueprint not found in {}".format(bp_file))
            return

        # Check if the given app name exists or generate random app name
        if app_name:
            res = get_app(app_name)
            if res:
                self.logger.debug(res)
                raise Exception("Application Name ({}) is already used.".format(app_name))
        else:
            app_name = "App{}".format(str(uuid.uuid4())[:10])

        # Get the blueprint type
        bp_type = bp_payload["spec"]["resources"].get("type", "")

        # Create blueprint from dsl file
        bp_name = "Blueprint{}".format(str(uuid.uuid4())[:10])
        self.logger.info("Creating blueprint {}".format(bp_name))
        res, err = create_blueprint(client=client, bp_payload=bp_payload, name=bp_name)
        if err:
            raise Exception(err["error"])

        bp = res.json()
        bp_state = bp["status"].get("state", "DRAFT")
        bp_uuid = bp["metadata"].get("uuid", "")

        if bp_state != "ACTIVE":
            self.logger.debug("message_list: {}".format(bp["status"].get("message_list", [])))
            raise Exception("Blueprint {} went to {} state".format(bp_name, bp_state))
        else:
            self.logger.info(
                "Blueprint {}(uuid={}) created successfully.".format(bp_name, bp_uuid)
            )

            runtime_vars = project.get("runtime_vars") or bp.get("runtime_vars")
            if runtime_vars:
                # open a new file for writing
                # todo get rid of launch_params file
                with open('launch_params.py', 'w') as f:
                    f.write('variable_list = ')
                    json.dump(bp.get('variable_list', []), f)
                    f.write('\n')

            # Creating an app
            try:
                self.logger.info("Creating app {}".format(app_name))
                launch_blueprint_simple(
                    blueprint_name=bp_name,
                    app_name=app_name,
                    launch_params="launch.params.py" if runtime_vars else None,
                    skip_app_name_check=True,
                )
            except Exception as e:
                raise e
            finally:
                if 'f' in locals():
                    f.close()
                # Delete the project file
                os.remove(f"launch_params.py") if os.path.exists(f"launch_params.py") else None

        return bp_uuid

    def verify(self, **kwargs):
        pass
