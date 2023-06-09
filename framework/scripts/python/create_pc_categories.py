from helpers.log_utils import get_logger
from scripts.python.helpers.v3.category import Category
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateCategoryPc(Script):
    """
    Class that creates Categories in PC
    """
    def __init__(self, data: dict):
        self.response = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(CreateCategoryPc, self).__init__()

    def execute(self, **kwargs):
        try:
            category = Category(self.pc_session)
            existing_categories_list = category.categories_with_values()

            if not self.data.get("categories"):
                logger.warning(f"Skipping category creation in {self.data['pc_ip']}")
                return

            category_list = []
            for category_to_create in self.data["categories"]:
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
                        data = {
                            "name": name,
                            "description": description
                        }
                        # We are using update as we need to use PUT to create categories
                        category.update(endpoint=name, data=data)

                    if values:
                        # add values to the category
                        category_list.append({
                            "name": name,
                            "values": values
                        })
                except Exception as e:
                    self.exceptions.append(f"Failed to create category {name}: {e}")

            if not category_list:
                logger.warning(f"No categories to create in {self.data['pc_ip']}")
                return

            logger.info(f"Batch create Categories in {self.data['pc_ip']}")
            category.batch_values_add(category_list)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # todo how to verify?
        pass
