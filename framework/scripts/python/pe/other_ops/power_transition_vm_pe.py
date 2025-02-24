from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.progress_monitor import TaskMonitor
from framework.scripts.python.helpers.state_monitor.vm_ip_monitor_pe import VmIpMonitorPe
from framework.scripts.python.helpers.v2.vm import VM
from framework.scripts.python.helpers.v1.vm import VM as VMV1
from framework.scripts.python.pe.cluster_script import ClusterScript

logger = get_logger(__name__)


class PowerTransitionVmPe(ClusterScript):
    """
    The Script to power Transition VMs in clusters
    """

    def __init__(self, data: Dict, **kwargs):
        super(PowerTransitionVmPe, self).__init__(data, **kwargs)
        self.transition = kwargs.get("transition", VM.ON)
        self.wait_for_ip_vm_name_list = []
        self.logger = self.logger or logger
        self.task_uuid_list = []

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):

        if not cluster_details.get("vms"):
            return

        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
            'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        try:
            if cluster_details.get("vms"):
                vm_op = VM(session=pe_session)
                vm_name_uuid_map = {vm["name"]: vm["uuid"] for vm in vm_op.read()}

                for vm_to_create in cluster_details["vms"]:
                    try:
                        vm_name = vm_to_create['name']
                        if vm_name not in vm_name_uuid_map:
                            self.logger.info(f"VM {vm_name!r} doesn't exist in {cluster_info!r}. "
                                             f"Skipping Power Transition to {self.transition}...")
                            continue

                        current_state = vm_op.get_vm_info(vm_name_list=[vm_name])[0].get("power_state")
                        if current_state == self.transition:
                            self.logger.info(f"VM {vm_name!r} is already in {self.transition!r} state in "
                                             f"{cluster_info!r}. Skipping...")
                            continue
                        if (self.transition is VM.ON or self.transition is VM.RESET or
                           self.transition is VM.GUEST_REBOOT):
                            self.wait_for_ip_vm_name_list.append(vm_name)
                        self.logger.info(f"Powering on VM {vm_name!r} in {cluster_info!r}")
                        response = vm_op.power_transition(vm_uuid=vm_name_uuid_map[vm_name],
                                                          transition=self.transition)

                        if response.get("task_uuid"):
                            self.logger.info(f"Submitted task {response['task_uuid']!r} for Powering ON of "
                                             f"VM {vm_name!r}")
                            self.task_uuid_list.append(response['task_uuid'])
                        else:
                            raise Exception(f"Could not create the VM {vm_name!r}. Error: {response}")
                    except Exception as e:
                        self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                               f"{cluster_info!r} with the error: {e}")

                # Monitor the tasks
                if self.task_uuid_list:
                    app_response, status = TaskMonitor(pe_session,
                                                       task_uuid_list=self.task_uuid_list).monitor()

                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append(f"Timed out. Powering ON of some or all VMs in {cluster_info!r} "
                                               f"didn't happen in the prescribed timeframe")

                # wait for IPs
                if self.wait_for_ip_vm_name_list:
                    self.logger.info(f"Waiting for IP address for VMs {self.wait_for_ip_vm_name_list} in "
                                     f"{cluster_info!r}")
                    app_response, status = VmIpMonitorPe(pe_session,
                                                         vm_name_list=self.wait_for_ip_vm_name_list).monitor()

                    if app_response and not status:
                        self.exceptions.append(f"Some VMs didn't get IP address. {app_response}")
            else:
                self.logger.info(f"No VMs specified in {cluster_info!r}. Skipping...")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info!r} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if network is created in PE
        try:
            if not cluster_details.get("vms"):
                return

            self.results["clusters"][cluster_ip] = {f"Power_{self.transition}_VM": {}}
            pe_session = cluster_details["pe_session"]

            vm_op = VMV1(pe_session)
            vm_list = []
            vm_name_info_map = {}

            for vm in cluster_details.get("vms"):
                # Set default status
                self.results["clusters"][cluster_ip][f"Power_{self.transition}_VM"][vm["name"]] = \
                    {"state": "CAN'T VERIFY"}

                vm_list = vm_list or vm_op.read()
                vm_name_info_map = (vm_name_info_map or
                                    {
                                        vm["vmName"]: (vm["powerState"],
                                                       vm.get("ipAddresses"))
                                        for vm in vm_list if vm.get("vmName")
                                    })

                if vm["name"] in vm_name_info_map:
                    self.results["clusters"][cluster_ip][f"Power_{self.transition}_VM"][vm["name"]]["state"] = \
                        "PASS" if (vm_name_info_map[vm["name"]][0] == self.transition) else "FAIL"
                    self.results["clusters"][cluster_ip][f"Power_{self.transition}_VM"][vm["name"]]["has_ip"] = \
                        "PASS" if (vm_name_info_map[vm["name"]][1]) else "FAIL"
                else:
                    self.results["clusters"][cluster_ip][f"Power_{self.transition}_VM"][vm["name"]]["state"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}")
