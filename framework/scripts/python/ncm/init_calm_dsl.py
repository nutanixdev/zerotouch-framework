import json
import sys
from typing import Dict
from copy import deepcopy
from calm.dsl.api import get_client_handle_obj, get_resource_api
from calm.dsl.config import set_dsl_config, get_default_db_file, get_default_local_dir, get_default_config_file
from calm.dsl.constants import DSL_CONFIG, POLICY, STRATOS
from distutils.version import LooseVersion as LV
from calm.dsl.cli.init_command import init_db, sync_cache, LOG
from framework.helpers.log_utils import get_logger
from framework.scripts.python.script import Script
from framework.helpers.helper_functions import read_creds

logger = get_logger(__name__)


class InitCalmDsl(Script):
    def __init__(self, data: Dict, **kwargs):
        self.data = deepcopy(data)
        super(InitCalmDsl, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            self.logger.info("Initializing Calm DSL...")
            host = self.data.get('ncm_vm_ip') or self.data['pc_ip']
            port = "9440"
            ncm_credential = self.data.get('ncm_credential') or self.data['pc_credential']
            # get credentials from the payload
            try:
                username, password = read_creds(data=self.data, credential=ncm_credential)
            except Exception as e:
                self.exceptions.append(e)
                sys.exit(1)
            project_name = self.data.get('default_ncm_project_name') or DSL_CONFIG.EMPTY_PROJECT_NAME

            # Get temporary client handle
            client = get_client_handle_obj(host=host, port=port, auth=(username, password))
            Obj = get_resource_api("services/nucalm/status", client.connection)
            res, err = Obj.read()

            if err:
                raise Exception("[{}] - {}".format(err["code"], err["error"]))

            result = json.loads(res.content)
            service_enablement_status = result["service_enablement_status"]
            self.logger.info(service_enablement_status)

            res, err = client.version.get_calm_version()
            if err:
                LOG.error("Failed to get version")
                sys.exit(err["error"])
            calm_version = res.content.decode("utf-8")

            # get policy status
            if LV(calm_version) >= LV(POLICY.MIN_SUPPORTED_VERSION):
                Obj = get_resource_api("features/policy", client.connection, calm_api=True)
                res, err = Obj.read()

                if err:
                    raise Exception("[{}] - {}".format(err["code"], err["error"]))
                result = json.loads(res.content)
                policy_status = (
                    result.get("status", {}).get("feature_status", {}).get("is_enabled", False)
                )
                LOG.info("Policy enabled={}".format(policy_status))
            else:
                LOG.debug("Policy is not supported")
                policy_status = False

            # get approval policy status
            if LV(calm_version) >= LV(POLICY.APPROVAL_POLICY_MIN_SUPPORTED_VERSION):
                Obj = get_resource_api(
                    "features/approval_policy", client.connection, calm_api=True
                )
                res, err = Obj.read()

                if err:
                    raise Exception("[{}] - {}".format(err["code"], err["error"]))
                result = json.loads(res.content)
                approval_policy_status = (
                    result.get("status", {}).get("feature_status", {}).get("is_enabled", False)
                )
                LOG.info("Approval Policy enabled={}".format(approval_policy_status))
            else:
                LOG.debug("Approval Policy is not supported")
                approval_policy_status = False

            # get stratos status
            if LV(calm_version) >= LV(STRATOS.MIN_SUPPORTED_VERSION):
                Obj = get_resource_api(
                    "features/stratos/status", client.connection, calm_api=True
                )
                res, err = Obj.read()

                if err:
                    raise Exception("[{}] - {}".format(err["code"], err["error"]))
                result = json.loads(res.content)
                stratos_status = (
                    result.get("status", {}).get("feature_status", {}).get("is_enabled", False)
                )
                LOG.info("stratos enabled={}".format(stratos_status))
            else:
                LOG.debug("Stratos is not supported")
                stratos_status = False
            if project_name != DSL_CONFIG.EMPTY_PROJECT_NAME:
                LOG.info("Verifying the project details")
                project_name_uuid_map = client.project.get_name_uuid_map(
                    params={"filter": "name=={}".format(project_name)}
                )
                if not project_name_uuid_map:
                    LOG.error("Project '{}' not found !!!".format(project_name))
                    sys.exit(-1)
                LOG.info("Project '{}' verified successfully".format(project_name))

            # calm_logger = LOG.get_logger()
            # print(calm_logger.handlers)
            # calm_logger.handlers.pop()
            # todo remove root logger handlers as we calm has it's own handlers

            # Not verifying project details
            set_dsl_config(
                host=host,
                port=port,
                username=username,
                password=password,
                project_name=DSL_CONFIG.EMPTY_PROJECT_NAME,
                db_location=get_default_db_file(),
                log_level="ERROR",
                local_dir=get_default_local_dir(),
                config_file=get_default_config_file(),
                retries_enabled=True,
                connection_timeout=10,
                read_timeout=300,
                policy_status=policy_status,
                approval_policy_status=approval_policy_status,
                stratos_status=stratos_status,
            )
            init_db()
            sync_cache()

            # todo initialize root logger handlers once done
            self.logger.info("DONE")
        except Exception as e:
            self.exceptions.append(e)
        # If SystemExit occurs, I shouldn't move onto other calm ops
        # except SystemExit as e:
        #     self.exceptions.append(e)

    def verify(self, **kwargs):
        self.logger.info(f"No verification needed for {type(self).__name__}")
        pass
