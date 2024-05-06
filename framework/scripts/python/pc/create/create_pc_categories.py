import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v3.category import Category
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateCategoryPc(Script):
    """
    Class that creates Categories in PC
    """
    def __init__(self, data: Dict, **kwargs):
        self.response = None
        self.data = data
        self.categories = self.data.get("categories")
        self.pc_session = self.data["pc_session"]
        super(CreateCategoryPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if not self.categories:
                self.logger.warning(f"No categories to create. Skipping category creation in {self.data['pc_ip']!r}")
                return

            category = Category(self.pc_session)
            existing_categories_list = category.categories_with_values()

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
                        data = {
                            "name": name,
                            "description": description
                        }
                        # We are using update as we need to use PUT to create categories
                        category.update(endpoint=name, data=data)

                    if values:
                        # add values to the category
                        self.logger.info(f"Adding values {values} to category {name} in {self.data['pc_ip']!r}")
                        category_list.append({
                            "name": name,
                            "values": values
                        })
                except Exception as e:
                    self.exceptions.append(f"Failed to create category {name}: {e}")

            if not category_list:
                self.logger.warning(f"No categories to create in {self.data['pc_ip']!r}")
                return

            self.logger.info(f"Trigger batch create API for Categories in {self.data['pc_ip']!r}")
            category.batch_values_add(category_list)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.categories:
            return

        # Initial status
        self.results["Create_Categories"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification
        time.sleep(5)
        category = Category(self.pc_session)
        existing_categories_list = []

        # todo modify verifications to include values
        for category_to_create in self.categories:
            name = category_to_create.get("name")

            # Initial status
            self.results["Create_Categories"][name] = "CAN'T VERIFY"
            existing_categories_list = existing_categories_list or category.categories_with_values()
            category_exists = next((existing_category for existing_category in existing_categories_list
                                    if existing_category["name"] == name), None)

            if category_exists:
                self.results["Create_Categories"][name] = "PASS"
            else:
                self.results["Create_Categories"][name] = "FAIL"
