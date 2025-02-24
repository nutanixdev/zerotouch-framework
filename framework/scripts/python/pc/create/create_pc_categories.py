import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class CreateCategoryPc(PcScript):
    """
    Class that creates Categories in PC
    """
    def __init__(self, data: Dict, **kwargs):
        self.response = None
        self.task_uuid_list = []
        self.data = data
        self.categories = self.data.get("categories")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(CreateCategoryPc, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.category_util = self.import_helpers_with_version_handling("Category")

    def execute(self):
        try:
            if not self.categories:
                self.logger.warning(f"No categories to create. Skipping category creation in {self.data['pc_ip']!r}")
                return

            existing_categories_list = self.category_util.categories_with_values()

            category_list = []
            for category_to_create in self.categories:
                name = category_to_create.get("name")
                description = category_to_create.get("description")
                values = category_to_create.get("values")

                category_exists = next((existing_category for existing_category in existing_categories_list
                                        if existing_category["name"] == name), None)

                try:
                    # Category is already there, just need to add values to the category
                    if category_exists:
                        values = [value_to_create for value_to_create in values
                                  if value_to_create not in category_exists["values"]]
                    else:
                        # create category first
                        self.logger.info(f"Creating category {name} in {self.data['pc_ip']!r}")
                        self.category_util.create_category(name, description)

                    if values:
                        # add values to the category
                        self.logger.info(f"Adding values {values} to category {name} in {self.data['pc_ip']!r}")
                        category_list.append({
                            "name": name,
                            "values": values,
                            "description": description
                        })
                except Exception as e:
                    self.exceptions.append(f"Failed to create category {name}: {e}")

            if not category_list:
                self.logger.warning(f"No categories to create in {self.data['pc_ip']!r}")
                return

            self.logger.info(f"Trigger batch create API for Categories in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.category_util.batch_values_add(category_list)
            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Creation of Categories in PC didn't happen in the"
                                           " prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.categories:
            return

        # Initial status
        self.results["Create_Categories"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification
        time.sleep(5)

        # todo modify verifications to include values
        existing_categories_list = []
        for category_to_create in self.categories:
            existing_categories_list = existing_categories_list or self.category_util.categories_with_values() 
            name = category_to_create.get("name")
            values = category_to_create.get("values")
            # Initial status
            self.results["Create_Categories"][name] = "CAN'T VERIFY"
            
            category_exists = False
            
            for existing_category in existing_categories_list:
                if ( existing_category["name"] == name and 
                all(item in existing_category["values"] for item in values) ):
                    category_exists = True
                    break
            if category_exists:
                self.results["Create_Categories"][name] = "PASS"
            else:
                self.results["Create_Categories"][name] = "FAIL"
