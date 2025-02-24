import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.pc.pc_script import PcScript
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor

logger = get_logger(__name__)


class DeleteCategoryPc(PcScript):
    """
    Class that deletes Categories in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.response = None
        self.tasks_uuid_list = []
        self.data = data
        self.categories = self.data.get("categories")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(DeleteCategoryPc, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.category_util = self.import_helpers_with_version_handling("Category")
  

    def execute(self):
        try:
            if not self.categories:
                self.logger.warning(f"No categories provided to delete in {self.data['pc_ip']!r}")
                return

            existing_categories_list = self.category_util.categories_with_values()

            for category_to_delete in self.categories:
                name = category_to_delete.get("name")
                category_exists = next((existing_category for existing_category in existing_categories_list
                                        if existing_category["name"] == name), None)

                # Check if Category is there
                if not category_exists:
                    self.logger.warning(f"No Category {category_to_delete.get('name')!r} in {self.data['pc_ip']!r}")
                    continue
                else:
                    self.tasks_uuid_list = self.category_util.batch_delete_values(
                        category_name=name, values=category_exists["values"])

                    if self.tasks_uuid_list:
                        app_response, status = TaskMonitor(
                            self.pc_session,
                            task_uuid_list=self.tasks_uuid_list,
                            task_op=self.import_helpers_with_version_handling('Task')).monitor()

                        if app_response:
                            self.exceptions.append(f"Some tasks have failed. {app_response}")

                        if not status:
                            self.exceptions.append(
                                "Timed out. Deletion of Categories in PC didn't happen in the prescribed timeframe"
                                )

                    if category_to_delete.get("delete_only_values"): #Not Applicable on v4
                        continue
                    response = self.category_util.delete(endpoint=name) #Not Applicable on v4
                    if str(response) == "<Response [200]>":
                        self.logger.info(f"Deletion of category {name} successful!")
                    else:
                        self.exceptions.append(f"Failed to delete category {name}: {response}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.categories:
            return

        # Initial status
        self.results["Delete_Categories"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification
        time.sleep(5)
        existing_categories_list = []

        # todo modify verifications to include values
        for category_to_delete in self.categories:
            name = category_to_delete.get("name")

            # Initial status
            self.results["Delete_Categories"][name] = "CAN'T VERIFY"
            existing_categories_list = existing_categories_list or self.category_util.categories_with_values()
            category_exists = next((existing_category for existing_category in existing_categories_list
                                    if existing_category["name"] == name), None)
            if not category_exists:
                self.results["Delete_Categories"][name] = "PASS"
            else:
                self.results["Delete_Categories"][name] = "FAIL"
