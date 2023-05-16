from typing import List

from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pc_entity import PcEntity
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class Category(PcEntity):
    kind = "category"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/categories"
        super(Category, self).__init__(session=session)

    def add_values(self, name: str, values: List):
        """
        Add values to a given PC category
        """
        self.batch_values_add(name, values)

    def get_values(self, name: str):
        """
        Get the values of the category.
        Args:
          name(str): The name of the category

        Returns:
          List<dict>, for example:
            ['policy_counts': '{}',
             'uuid': 'f312d033-c03e-47f3-b77b-78e7ee5e3430',
             'value': u'2',
             'entity_counts': '{}'}]
        """
        endpoint = f"{name}/list"
        values = self.list(use_base_url=True, endpoint=endpoint)
        return values

    def categories_with_values(self):
        category_entity_list = self.list()
        for category in category_entity_list:
            category["values"] = [value.get("value")
                                  for value in self.get_values(category["name"])]

        return category_entity_list

    def batch_values_add(self, category_list: List, **kwargs):
        requests = []

        for category in category_list:
            name = category["name"]
            values = category["values"]
            endpoint = name
            operation = kwargs.get("operation", "PUT")
            # todo
            base_url = f"api/nutanix//v3{self.resource_type}/{endpoint}"

            for value in values:
                requests.append(
                    {
                        "operation": operation,
                        "body": {"value": value, "description": name},
                        "path_and_params": f"{base_url}/{value}"
                    }
                )

        return self.batch_op.batch(api_request_list=requests)
