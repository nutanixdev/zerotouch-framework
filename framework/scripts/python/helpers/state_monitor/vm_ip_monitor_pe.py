from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .state_monitor import StateMonitor
from ..v1.vm import VM

logger = get_logger(__name__)


class VmIpMonitorPe(StateMonitor):
    """
    Class to wait for vm ip address after powered on/reboot/reset/powercycle
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 30
    DEFAULT_TIMEOUT_IN_SEC = 2 * 60

    def __init__(self, session: RestAPIUtil, vm_name_list: list):
        """
          The constructor for VmIpMonitor
          Args:
            session: request session to query the API
            vm_name_list(list): List of VM names to be verified
          """
        self.vm_info = None
        self.powered_on_vms = 0
        self.session = session
        self.vm_name_list = vm_name_list
        self.vms_with_ip = []
        self.vm_op = VM(self.session)

    @property
    def vms_without_ip(self):
        return list(set(self.vm_name_list) - set(self.vms_with_ip))

    def check_status(self):
        """
        Check whether VMs are assigned with IP address

        Returns:
          bool: True
        """
        response = None
        self.vm_info = self.vm_op.get_vm_info(vm_name_list=self.vms_without_ip)

        for vm in self.vm_info:
            if vm.get("powerState") == VM.ON and vm.get("ipAddresses"):
                self.vms_with_ip.append(vm["vmName"])

        if len(self.vms_with_ip) == len(self.vm_name_list):
            completed = True
        else:
            completed = False
            response = self.vms_without_ip
        logger.info(f"{len(self.vms_with_ip)}/{len(self.vm_name_list)} VMs have IP address")
        return response, completed
