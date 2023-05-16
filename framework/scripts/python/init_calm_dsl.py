from helpers.log_utils import get_logger
from scripts.python.script import Script
from calm.dsl.cli import set_server_details, init_db, sync_cache

logger = get_logger(__name__)


class InitCalmDsl(Script):
    def __init__(self, data: dict):
        self.data = data
        super(InitCalmDsl, self).__init__()

    def execute(self, **kwargs):
        try:
            logger.info("Initializing Calm DSL...")
            set_server_details(
                ip=self.data['pc_ip'],
                port="9440",
                username=self.data['pc_username'],
                password=self.data['pc_password'],
                project_name=self.data['project_name'],
                config_file=None,
                local_dir=None,
                db_file=None
            )
            init_db()
            sync_cache()
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        logger.info(f"No verification needed for {type(self).__name__}")
        pass
