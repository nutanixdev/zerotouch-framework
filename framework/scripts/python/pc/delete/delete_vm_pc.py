from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.v3.vm import VM
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteVmPc(Script):
    """
    Class that Deletes VMs in PC
    """

    def __init__(self, data: Dict, **kwargs):
        """
        Class to delete images from PC
        """
        self.data = data
        self.pc_session = data["pc_session"]
        self.vms_list = data.get("vms")
        super(DeleteVmPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        try:
            if self.data.get("vms"):
                vm_op = VM(self.pc_session)

                self.vm_cluster_name_dict = {
                    vm["name"]: vm["cluster_name"] for vm in self.vms_list
                }
                self.vms_to_delete_uuid_list = [
                    vm.get("metadata").get("uuid") for vm in vm_op.list()
                    if vm.get("spec", {}).get("name") in self.vm_cluster_name_dict.keys()
                    and vm.get("spec", {}).get("cluster_reference", {}).get("name")
                    == self.vm_cluster_name_dict[vm.get("spec", {}).get("name")]
                ]

                if self.vms_to_delete_uuid_list:
                    self.task_uuid_list = vm_op.batch_delete_vm(
                        self.vms_to_delete_uuid_list
                    )

                    if self.task_uuid_list:
                        app_response, status = TaskMonitor(
                            self.pc_session, task_uuid_list=self.task_uuid_list
                        ).monitor()

                        if app_response:
                            self.exceptions.append(
                                f"Some tasks have failed. {app_response}"
                            )

                        if not status:
                            self.exceptions.append(
                                "Timed out. Delete VMs in PC didn't happen in the prescribed timeframe"
                            )
                else:
                    self.logger.info("No VMs to Delete")

        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        # Initial status
        if self.vms_list:
            self.results["DeleteVM"] = {}
            try:
                vm_op = VM(self.pc_session)
                # Get Exisiting VM names with Cluster names from PC
                # Stored as a tuple in format (VM_name, Cluster_name)
                exisitng_vms = [
                    (vm.get("spec", {}).get("name"), vm.get("spec", {}).get("cluster_reference", {}).get("name"))
                    for vm in vm_op.list()
                ]
                for vm_name,cluster_name in self.vm_cluster_name_dict.items():
                    self.results["DeleteVM"][vm_name] = "CAN'T VERIFY"

                    # Updating the result as PASS if the VMs are not present in PC
                    if (vm_name, cluster_name) not in exisitng_vms:
                        self.results["DeleteVM"][vm_name] = "PASS"
                    else:
                        self.results["DeleteVM"][vm_name] = "FAIL"

            except Exception as e:
                self.exceptions.append(e)
