from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pc_entity import PcEntity


class Service(PcEntity):
    kind = "service"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/services"
        super(Service, self).__init__(session)

    def get_microseg_status(self):
        """
        Get the service status
        Returns:
          str, for example, ENABLED, ENABLING
        """
        return self._get_service_status("microseg")

    def get_dr_status(self):
        """
        Get the service status
        Returns:
          str, for example, ENABLED, ENABLING
        """
        return self._get_service_status("disaster_recovery")

    def enable_microseg(self):
        """
        Enable microseg service
        Returns:
          {"task_uuid": "9063a53d-e043-4c2c-807b-fd8de3168604"}
        """
        return self._enable_service("microseg")

    def enable_leap(self):
        """
        Enable leap service
        Returns:
          {"task_uuid": "9063a53d-e043-4c2c-807b-fd8de3168604"}
        """
        return self._enable_service("disaster_recovery")

    def _get_service_status(self, name: str):
        """
        Get the service status
        Args:
          name(str): The name of the service
        Returns:
          str, for example, ENABLED, ENABLING
        """
        endpoint = f"{name}/status"
        response = self.read(endpoint=endpoint)
        return response.get("service_enablement_status")

    def _enable_service(self, name: str):
        """
        Enable the service
        Args:
          name(str): The name of the service
        Returns:
          dict, the api response. example:
              {"task_uuid": "9063a53d-e043-4c2c-807b-fd8de3168604"}
        """
        endpoint = name
        payload = {
            'state': 'ENABLE'
        }
        return self.create(data=payload, endpoint=endpoint)
