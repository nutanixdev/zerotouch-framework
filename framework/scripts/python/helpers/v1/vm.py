from typing import Optional, Dict, Union, List
from ..pe_entity_v1 import PeEntityV1
from framework.helpers.rest_utils import RestAPIUtil


class HYPERVISOR:
    """
  Hypervisor Constants
  """
    AHV = "AHV"
    ESXI = "ESXI"


class VM(PeEntityV1):
    ON = "on"
    OFF = "off"
    PAUSE = "pause"
    RESUME = "resume"
    SUSPEND = "suspend"
    GUEST_REBOOT = "acpi_reboot"
    GUEST_SHUTDOWN = "acpi_shutdown"
    RESET = "reset"
    POWER_CYCLE = "powercycle"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/vms"
        self.session = session
        super(VM, self).__init__(session=session)

    def get_spec(self, params: Optional[Dict] = None, spec: Optional[dict] = None) -> (Optional[Dict], Optional[str]):
        raise NotImplementedError(f"get_spec method is not implemented for  {type(self).__name__}")

    def update(
        self,
        data=None,
        endpoint=None,
        query=None,
        timeout=None,
        method="PUT"
    ):
        raise NotImplementedError(f"update method is not implemented for  {type(self).__name__}")

    def delete(
        self,
        uuid=None,
        timeout=None,
        endpoint=None,
        query=None,
    ):
        raise NotImplementedError(f"delete method is not implemented for  {type(self).__name__}")
    # 
    # def read(
    #     self,
    #     uuid=None,
    #     method="GET",
    #     data=None,
    #     endpoint=None,
    #     query=None,
    #     timeout=None,
    #     entity_type=None,
    #     custom_filters=None
    # ):
    #     raise NotImplementedError(f"read method is not implemented for  {type(self).__name__}")

    def list(
        self,
        endpoint=None,
        use_base_url=False,
        data=None,
        custom_filters=None,
        timeout=None,
        entity_type=None
    ) -> Union[List, Dict]:
        raise NotImplementedError("list method is not implemented for Auth")

    def upload(
        self,
        source,
        data,
        endpoint="import_file",
        query=None,
        timeout=30,
    ):
        raise NotImplementedError("upload method is not implemented for Auth")

    def get_vm_info(self, vm_name_list: List) -> List[dict]:
        vm_name_list = ",".join([f"vm_name=={vm_name}" for vm_name in vm_name_list])
        query = {
            "filterCriteria": f"is_cvm==0;{vm_name_list}"
        }
        return self.read(query=query)
