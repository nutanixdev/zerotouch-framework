import os
from calm.dsl.cli.projects import update_project_from_dsl
from helpers.log_utils import get_logger
from scripts.python.script import Script
from jinja2 import Template

logger = get_logger(__name__)


class UpdateCalmProject(Script):
    def __init__(self, data: dict):
        self.data = data
        super(UpdateCalmProject, self).__init__()

    def execute(self, **kwargs):
        logger.info("Update the project...")
        helper_directory = f"{self.data['project_root']}/framework/scripts/python/helpers"
        project_update_helper = "update_project_dsl.py.jinja"

        with open(f"{helper_directory}/{project_update_helper}", 'r') as f:
            template = Template(f.read())
            data = {
                'NTNX_ACCOUNT': self.data['account_name'],
                'SUBNET_CLUSTER_MAPPING': self.data['subnets']
            }
            output = template.render(data)

        project_file = "update_project_dsl.py"
        try:
            with open(f"{helper_directory}/{project_file}", 'w') as f:
                f.write(output)

            update_project_from_dsl(
                self.data['project_name'],
                f"{helper_directory}/{project_file}",
                no_cache_update=False,
                append_only=True
            )
        except Exception as e:
            raise e
        finally:
            if 'f' in locals():
                f.close()
            # Delete the project file
            os.remove(f"{helper_directory}/{project_file}")

    def verify(self, **kwargs):
        # no verification needed for dsl
        pass
