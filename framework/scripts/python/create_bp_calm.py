from calm.dsl.api import get_api_client
from helpers.log_utils import get_logger
from scripts.python.script import Script
from calm.dsl.cli import create_blueprint_from_dsl

logger = get_logger(__name__)


class CreateBp(Script):
    def __init__(self, data: dict):
        self.data = data
        super(CreateBp, self).__init__()

    def execute(self, **kwargs):
        try:
            # Get the BPs list
            for bp in self.data["bp_list"]:
                logger.info(f"Creating Blueprint {bp['name']}")
                bp_file = f"{self.data['project_root']}/{bp['dsl_file']}"

                try:
                    client = get_api_client()

                    create_blueprint_from_dsl(
                        client=client,
                        name=bp['name'],
                        force_create=True,
                        bp_file=bp_file
                    )
                    logger.info(f"Created {bp['name']} successfully!")
                except Exception as e:
                    self.exceptions.append(f"Failed to create BP {bp_file}: {e}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        pass
