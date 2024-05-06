from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class User(PeEntityV1):
    """
    Class to create/update/delete/read local users and roles
    """

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/users"
        super(User, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    @staticmethod
    def get_payload(user_name: str, user_password: str, first_name: str, last_name: str):
        return {
            'profile': {
                'username': user_name,
                'password': user_password,
                'first_name': first_name,
                'last_name': last_name
            }
        }

    def create_new_role(self, user_name: str, role_list: list) -> Dict:
        endpoint = f"{user_name}/roles"
        return super().create(data=role_list, endpoint=endpoint)

    def create_user(self, user_name: str, user_password: str, first_name: str, last_name: str) -> dict:
        return super().create(data=self.get_payload(user_name, user_password, first_name, last_name))

    def update(self, **kwargs):
        super().update(data=self.get_payload(**kwargs))
