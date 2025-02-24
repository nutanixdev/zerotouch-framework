from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.state_monitor.vm_ip_monitor_pc import VmIpMonitorPc
from framework.scripts.python.helpers.v3.vm import VM, VmPowerState
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class PowerOnVmPc(Script):
    """
    Class that Powers on VMs in PC
    """

    def __init__(self, data: Dict, cluster_name: str, **kwargs):
        """
        Args:
            data (dict): _description_
            cluster_name (str): _description_
            kwargs:
                vm_name_list (list, optional): List of VM names to power on. Optional, if vm_list is passed
                vm_list (list, optional): List of VM info to power on. Optional, if vm_name_list is passed
        """
        self.task_uuid_list = []
        self.pc_session = data["pc_session"]
        self.pe_cluster = cluster_name
        self.vm_name_list = kwargs.get("vm_name_list", [])
        self.vm_list = kwargs.get("vm_list", [])
        self.vms_to_power_on = []
        super(PowerOnVmPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            vm_op = VM(self.pc_session)

            # Get VM info list if only VM names are passed
            filter_criteria = f"cluster_name=={self.pe_cluster}"
            if not self.vm_list and self.vm_name_list:
                self.vm_list = [vm for vm in vm_op.list(filter=filter_criteria) if vm.get("spec", {}).get("name")
                                in self.vm_name_list]

            # Filter the VMs which are in state power OFF state
            # todo Incorrect logic
            self.vms_to_power_on = vm_op.list(timeout=120, custom_filters={"power_state": VmPowerState.OFF})
            self.vms_to_power_on = [{"uuid": vm["metadata"]["uuid"], "spec": vm["spec"], "metadata": vm["metadata"]}
                                    for vm in self.vms_to_power_on]
            if self.vms_to_power_on:
                self.task_uuid_list = vm_op.batch_power_on_vm(self.vms_to_power_on)

                if self.task_uuid_list:
                    app_response, status = TaskMonitor(self.pc_session, task_uuid_list=self.task_uuid_list).monitor()

                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append(
                            "Timed out. Power On VMs in PC didn't happen in the prescribed timeframe")
            else:
                self.logger.info("No VMs to Power ON")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        if self.vms_to_power_on:
            self.results["PowerOnVM"] = {}
            try:
                vm_op = VM(self.pc_session)
                # Get Existing VM info list from PC
                filter_criteria = f"cluster_name=={self.pe_cluster}"
                if not self.vm_name_list:
                    self.vm_name_list = [vm.get("spec", {}).get("name") for vm in self.vm_list]

                # Filter all the VMs which are in power ON state
                existing_vm_list = vm_op.list(timeout=120, filter=filter_criteria,
                                              custom_filters={"power_state": VmPowerState.ON})
                self.logger.debug(f"existing_vm_list: {len(existing_vm_list)}")

                # Check if the VMs created are in existing power ON vm list
                vm_powered_on_list = [vm for vm in existing_vm_list if vm.get("spec", {}).get("name") in
                                      self.vm_name_list]
                self.logger.debug(f"vm_powered_on_list: {len(vm_powered_on_list)}")

                # Updating the result as PASS if the VMs are in powered_on_list
                self.results["PowerOnVM"].update({vm["spec"]["name"]: "PASS" for vm in vm_powered_on_list})
                if len(self.vm_name_list) == len(vm_powered_on_list):
                    self.logger.info(f"{len(vm_powered_on_list)} VMs are Powered ON")
                else:
                    vms_failed_power_on_list = [val["spec"]["name"] for val in self.vm_list if val not in
                                                existing_vm_list]
                    self.results["PowerOnVM"].update({vm: "FAIL" for vm in vms_failed_power_on_list})
                    self.exceptions.append(f"Failed to power on VMs: {vms_failed_power_on_list}")

                # Check VM VIP status
                self.logger.info("Check VM IP status")
                if vm_powered_on_list:
                    vm_uuid_list = [val["metadata"]["uuid"] for val in vm_powered_on_list]
                    _, status = VmIpMonitorPc(self.pc_session, vm_uuid_list=vm_uuid_list).monitor()

                    if status:
                        logger.info(f"{len(vm_powered_on_list)} VMs are assigned with IP Address")
            except Exception as e:
                self.exceptions.append(e)
