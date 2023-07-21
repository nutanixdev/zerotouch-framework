import json

from calm.dsl.api import get_client_handle_obj, get_resource_api
from calm.dsl.config import set_dsl_config, get_default_db_file, get_default_local_dir, get_default_config_file
from helpers.log_utils import get_logger
from scripts.python.script import Script
from calm.dsl.cli.init_command import init_db, sync_cache

logger = get_logger(__name__)


class InitCalmDsl(Script):
    def __init__(self, data: dict, **kwargs):
        self.data = data
        super(InitCalmDsl, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            self.logger.info("Initializing Calm DSL...")
            host = self.data.get('ncm_vm_ip') or self.data['pc_ip']
            port = "9440"
            username = self.data.get('ncm_username') or self.data['pc_username']
            password = self.data.get('ncm_password') or self.data['pc_password']

            # Get temporary client handle
            client = get_client_handle_obj(host=host, port=port, auth=(username, password))
            Obj = get_resource_api("services/nucalm/status", client.connection)
            res, err = Obj.read()

            if err:
                raise Exception("[{}] - {}".format(err["code"], err["error"]))

            result = json.loads(res.content)
            service_enablement_status = result["service_enablement_status"]
            self.logger.info(service_enablement_status)

            # Not verifying project details
            set_dsl_config(
                host=host,
                port=port,
                username=username,
                password=password,
                project_name=self.data.get('default_ncm_project_name') or self.data['project_name'],
                db_location=get_default_db_file(),
                log_level="INFO",
                local_dir=get_default_local_dir(),
                config_file=get_default_config_file(),
                retries_enabled=True,
                connection_timeout=10,
                read_timeout=300,
            )
            init_db()
            sync_cache()
            self.logger.info("DONE")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        self.logger.info(f"No verification needed for {type(self).__name__}")
        pass
