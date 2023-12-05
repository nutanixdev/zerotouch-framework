from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .state_monitor import StateMonitor
from ..v3.vm import VM

logger = get_logger(__name__)


class VmIpMonitor(StateMonitor):
    """
    Class to wait for vm ip address after powered on/reboot/reset/powercycle
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 30
    DEFAULT_TIMEOUT_IN_SEC = 2 * 60

    def __init__(self, session: RestAPIUtil, vm_uuid_list):
        """
          The constructor for VmIpMonitor
          Args:
            session: request session to query the API
            vm_uuid_list(list): List of UUIDs of VMs to be verified
          """
        self.session = session
        self.vm_uuid_list = vm_uuid_list

    def check_status(self):
        """
        Check whether VMs are assigned with IP address

        Returns:
          bool: True
        """
        response = None

        vm_op = VM(self.session)
        # Exclude the VMs that are not in power on state.
        powered_on_vms = vm_op.list(timeout=120, custom_filters={"power_state": "ON"})
        vm_info_list = vm_op._filter_vm_by_uuid(powered_on_vms, self.vm_uuid_list)
        vms_without_ip = [vm for vm in vm_info_list if not vm_op._get_vm_ip_address(vm)]
        if not vms_without_ip:
            completed = True
        else:
            completed = False
            response = vms_without_ip
        logger.info("[{}/{}] Tasks Completed".format(len(self.vm_uuid_list) - len(vms_without_ip),
                                                     len(self.vm_uuid_list)))
        return response, completed
