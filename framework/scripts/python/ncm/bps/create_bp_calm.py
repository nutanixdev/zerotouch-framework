from pathlib import Path
from typing import Union, Dict
from calm.dsl.api import get_api_client
from calm.dsl.builtins import SimpleBlueprint, Ref, VmBlueprint, create_blueprint_payload, get_dsl_metadata_map
from calm.dsl.builtins.models.metadata_payload import get_metadata_payload
from calm.dsl.cli import create_app
from calm.dsl.cli.bps import get_blueprint_module_from_file, get_blueprint_class_from_module, create_blueprint
from calm.dsl.config import get_context
from framework.helpers.log_utils import get_logger
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateBp(Script):
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        super(CreateBp, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def compile_blueprint(self, bp_file: Union[str, Path], project_name: str):
        # compile_blueprint function needs file as input, so modifying the logic for
        # non-brownfield_deployment_file BPs

        metadata_payload = get_metadata_payload(bp_file)

        user_bp_module = get_blueprint_module_from_file(bp_file)

        # Here is where we are modifying non-run time variables like ACCOUNT_NAME
        if getattr(user_bp_module, "ACCOUNT_NAME", None) and self.data.get("account_name"):
            user_bp_module.ACCOUNT_NAME = self.data["account_name"]

        # Here is where we are modifying non-run time variables like CLUSTER_NAME
        if getattr(user_bp_module, "ACCOUNT_NAME", None) and self.data.get("account_name"):
            user_bp_module.ACCOUNT_NAME = self.data["account_name"]

        # Here is where we are modifying non-run time variables like SUBNET
        if getattr(user_bp_module, "ACCOUNT_NAME", None) and self.data.get("account_name"):
            user_bp_module.ACCOUNT_NAME = self.data["account_name"]

        UserBlueprint = get_blueprint_class_from_module(user_bp_module)
        if UserBlueprint is None:
            return None

        ContextObj = get_context()
        project_config = ContextObj.get_project_config()

        if project_name:
            project_config["name"] = project_name

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
            # Get the BPs list
            for bp in self.data["bp_list"]:
                self.logger.info(f"Creating Blueprint {bp['name']}")
                bp_file = f"{self.data['project_root']}/{bp['dsl_file']}"
                try:
                    client = get_api_client()

                    # payload = getattr(create_app, "bp_payload")
                    bp_payload = self.compile_blueprint(bp_file=bp_file, project_name=self.data.get("project_name"))
                    if bp_payload is None:
                        err_msg = "User blueprint not found in {}".format(bp_file)
                        err = {"error": err_msg, "code": -1}
                        return None, err

                    create_blueprint(
                        client=client,
                        bp_payload=bp_payload,
                        name=bp['name'],
                        force_create=True,
                    )

                    self.logger.info(f"Created {bp['name']} successfully!")
                except Exception as e:
                    self.exceptions.append(f"Failed to create BP {bp_file}: {e}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        pass
