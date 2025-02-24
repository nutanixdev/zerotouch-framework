from typing import List
from framework.helpers.v4_api_client import ApiClientV4
from ..pc_batch_op_v4 import PcBatchOpv4

import ntnx_prism_py_client

class Category:
    kind = "categories"
    # Configure the client
    def __init__(self, v4_api_util: ApiClientV4):
        self.resource_type = "prism/v4.0/config/categories"
        self.kind = "Category"
        self.client = v4_api_util.get_api_client("prism")
        self.categories_api = ntnx_prism_py_client.CategoriesApi(
            api_client=self.client
            )
        self.batch_op = PcBatchOpv4(v4_api_util, resource_type=self.resource_type, kind=self.kind)

    # def add_values(self, name: str, values: List):
    #     """
    #     Add values to a given PC category
    #     """
    #     self.batch_values_add(name, values)


    def get_categories(self, **kwargs):
        try:
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
            category_entity_list = self.categories_api.list_categories(**headers)
            return category_entity_list.to_dict()
        except ntnx_prism_py_client.rest.ApiException as e:
            raise Exception(f"Failed to get categories: {e}")
    
    def get_category_ext_id(self, category_name: str, value: str):
        filter_query = f"key eq '{category_name}' and value eq '{value}'"
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        category = self.categories_api.list_categories(_filter=filter_query, **headers)
        if category.data:
            return category.data[0].ext_id
        else:
            return None

    def create_category(self, name: str, description: str = None):
        pass
        #Skipping This Method as it is not required in v4 API but only in v3 API

    def categories_with_values(self) -> List:
        categories_response = self.get_categories()
        category_value_dict = {}
        for category in categories_response["data"]:
            if not category_value_dict.get(category["key"]):
                category_value_dict[category["key"]] = [category["value"]]
            else:
                category_value_dict[category["key"]].append(category["value"])
        categories_with_values = [{"name": key, "values": value} for key, value in category_value_dict.items()]
        return categories_with_values

    def batch_values_add(self, category_list: List):
        # This method does Create Values with Category.
        batch_payload = []
        
        for category in category_list:
            name = category["name"]
            values = category["values"]
            description = category.get("description", None)
            # todo

            for value in values:
                data = {"key": name, "value": value}
                if description:
                    data["description"] = description
                batch_payload.append(data)
        return self.batch_op.batch_create(request_payload_list = batch_payload)

    def batch_delete_values(self, category_name: str, values: List):
        # This method does Delete Values with Category.
        batch_payload = []
        for value in values:
            extId = self.get_category_ext_id(category_name, value)
            category_obj = self.categories_api.get_category_by_id(extId)
            etag = self.client.get_etag(category_obj.data)
            batch_payload.append((extId, etag))
        return self.batch_op.batch_delete(batch_payload)

    @staticmethod
    def delete(endpoint: str): #In v3 There is a delete method which accepts endoint as argument, This is just to bypass that
        return "<Response [200]>" #Skipping This since it is not required in v4 API