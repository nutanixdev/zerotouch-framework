from copy import deepcopy
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v3.vm import VM
from framework.scripts.python.helpers.v3.ova import Ova
from framework.scripts.python.script import Script
from framework.scripts.python.helpers.v3.network import Network
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.scripts.python.helpers.v3.cluster import Cluster as PcCluster

logger = get_logger(__name__)


class PcOvaDeployVM(Script):
    """
    Class that deploys OVAs as VMs in PC
    """

    def __init__(self, data: Dict, cluster_name: str, ova_name: str, new_vm_spec_list: list, **kwargs):
        """
        The default constructor for the PcOvaDeployVM.

        Args:
            data (dict): Configration file data
            cluster_name (str): Cluster Name
            ova_name (str): OVA Name
            new_vm_spec_list (list): New VM Spec list
            Eg: [
                {
                    vm_name: vm-01
                    subnet_name: vlan-01
                }
            ]
        """
        self.pc_session = data["pc_session"]
        self.cluster_name = cluster_name
        self.ova_name = ova_name
        self.new_vm_spec_list = new_vm_spec_list
        self.task_uuid_list = None
        super(PcOvaDeployVM, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        """
        Use Batch to deploy OVA as VMs
        Returns:
        None
        """
        try:
            pc_ova = Ova(session=self.pc_session)
            pc_cluster = PcCluster(self.pc_session)
            pc_cluster.get_pe_info_list()
            cluster_uuid = pc_cluster.name_uuid_map.get(self.cluster_name)
            ova_info = pc_ova.get_ova_by_cluster_reference(ova_name=self.ova_name, cluster_uuid=cluster_uuid)
            self.logger.info(f"ova_info: {ova_info}")
            if ova_info:
                # VM Spec from the OVA
                ova_vm_spec = pc_ova.get_vm_spec_from_ova_uuid(ova_info["metadata"]["uuid"])
                self.logger.info(f"ova_vm_spec: {ova_vm_spec}")

            request_payload_list = []
            # Update Create VM Spec
            for new_vm_spec in self.new_vm_spec_list:
                if new_vm_spec["subnet_name"]:
                    network = Network(self.pc_session)
                    network_uuid = network.get_uuid_by_name(
                        cluster_name=self.cluster_name, subnet_name=new_vm_spec["subnet_name"])
                    new_vm_spec["nic_list"] = [{
                        "is_connected": True,
                        "subnet_reference": {
                            "uuid": network_uuid,
                            "kind": "subnet"
                        }
                    }]
                    new_vm_spec.pop('subnet_name')

                # Copy the ova vm spec and update with new vm spec
                vm_spec = deepcopy(ova_vm_spec)
                for key, value in new_vm_spec.items():
                    if key == "vm_name":
                        vm_spec["name"] = value
                    elif vm_spec["resources"].get(key):
                        vm_spec["resources"][key] = value
                # TODO: Add support for static ip
                # Updating the cluster reference where the VM needs to be created.
                vm_spec["cluster_reference"] = {"kind": "cluster", "uuid": cluster_uuid, "name": self.cluster_name}
                request_payload_list.append({
                    "spec": vm_spec,
                    "metadata": {
                        "kind": "vm"
                    },
                    "api_version": "3.1.0"
                })

            # Batch create VMs
            vm = VM(self.pc_session)
            self.task_uuid_list = vm.batch_create_vm(vm_create_payload_list=request_payload_list)
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(self.pc_session,
                                                     task_uuid_list=self.task_uuid_list).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed while creating VM. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Creation of VMs in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        """Verify if VM Exists
        """
        # Initial Status
        self.results["Deploy_OVA_As_VM"] = {}
        try:
            vm = VM(self.pc_session)
            for vm_spec in self.new_vm_spec_list:
                filter_criteria = f"vm_name=={vm_spec['vm_name']};cluster_name=={self.cluster_name}"
                vm_response = vm.list(filter=filter_criteria)
                if len(vm_response) > 0:
                    self.results["Deploy_OVA_As_VM"][vm_spec["vm_name"]] = "PASS"
                else:
                    self.results["Deploy_OVA_As_VM"][vm_spec["vm_name"]] = "FAIL"
        except Exception as e:
            self.logger.error(e)
