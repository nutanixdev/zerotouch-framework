import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v3.category import Category
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteCategoryPc(Script):
    """
    Class that deletes Categories in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.response = None
        self.data = data
        self.categories = self.data.get("categories")
        self.pc_session = self.data["pc_session"]
        super(DeleteCategoryPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if not self.categories:
                self.logger.warning(f"No categories to delete. Skipping category delete in {self.data['pc_ip']!r}")
                return

            category = Category(self.pc_session)
            existing_categories_list = category.categories_with_values()

            for category_to_delete in self.categories:
                name = category_to_delete.get("name")
                category_exists = next((existing_category for existing_category in existing_categories_list
                                        if existing_category["name"] == name), None)

                # Check if Category is there
                if not category_exists:
                    self.logger.warning(f"No Category {category_to_delete.get('name')!r} in {self.data['pc_ip']!r}")
                    continue
                else:
                    category.batch_delete_values(category_name=name, values=category_exists["values"])
                    if category_to_delete.get("delete_only_values"):
                        continue
                    response = category.delete(endpoint=name)
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
        category = Category(self.pc_session)
        existing_categories_list = []

        # todo modify verifications to include values
        for category_to_delete in self.categories:
            name = category_to_delete.get("name")

            # Initial status
            self.results["Delete_Categories"][name] = "CAN'T VERIFY"
            existing_categories_list = existing_categories_list or category.list()
            category_exists = next((existing_category for existing_category in existing_categories_list
                                    if existing_category["name"] == name), None)
            if not category_exists:
                self.results["Delete_Categories"][name] = "PASS"
            else:
                self.results["Delete_Categories"][name] = "FAIL"
