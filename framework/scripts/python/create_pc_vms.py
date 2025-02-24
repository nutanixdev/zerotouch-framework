from typing import Dict
from framework.helpers.log_utils import get_logger
from .helpers.pc_groups_op import PcGroupsOp
from .helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from .helpers.v3.cluster import Cluster as PcCluster
from .helpers.v3.vm import VM
from .script import Script

logger = get_logger(__name__)


class CreateVmsPc(Script):
    """
    Class that creates VMs in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        # pass the Cluster Objects
        # create_pe_pc helper function can be used
        self.pe_clusters = self.data.get("clusters", {})
        super(CreateVmsPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            vm_obj = VM(session=self.pc_session)
            vms_to_create = []

            for _, cluster_details in self.pe_clusters.items():
                for vm_info in cluster_details.get("vms", []):
                    cluster_name = cluster_details["cluster_info"]["name"]
                    cluster_uuid = cluster_details["cluster_info"].get("uuid")

                    if not cluster_uuid:
                        pc_cluster = PcCluster(self.pc_session)
                        pc_cluster.get_pe_info_list()
                        cluster_uuid = pc_cluster.name_uuid_map.get(cluster_name)
                        if not cluster_uuid:
                            self.exceptions.append(f"Failed to create VMs in {cluster_name}")
                            continue

                    filter_criteria = f"cluster_name=={cluster_name};vm_name=={vm_info['name']}"

                    vms_response = vm_obj.list(filter=filter_criteria)

                    if len(vms_response) > 0:
                        self.logger.warning(f"Skipping VM creation. VM {vm_info['name']} already exists in the cluster {cluster_name}")
                    else:
                        try:
                            payload = vm_obj.create_pc_vm_payload(cluster_name=cluster_name, **vm_info)
                            vms_to_create.append(payload)
                        except Exception as e:
                            self.exceptions.append(f"Failed to create VM {vm_info['name']}: {e}")

            if not vms_to_create:
                self.logger.warning(f"No VMs to create in '{self.data['pc_ip']}'")
                return

            self.logger.info(f"Batch create VMs in '{self.data['pc_ip']}'")
            self.task_uuid_list = vm_obj.batch_create_vm(vms_to_create)

            if self.task_uuid_list:
                pc_task_monitor = PcTaskMonitor(self.pc_session,
                                                task_uuid_list=self.task_uuid_list)
                pc_task_monitor.DEFAULT_CHECK_INTERVAL_IN_SEC = 10
                pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC = 600
                app_response, status = pc_task_monitor.monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Creation of VMs in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        self.results["clusters"] = {}

        for cluster_ip, cluster_details in self.pe_clusters.items():
            try:
                self.results["clusters"][cluster_ip] = {"Create_VMs": {}}
                if not cluster_details.get("vms"):
                    continue

                vm_obj = VM(session=self.pc_session)
                for vm_info in cluster_details.get("vms", []):
                    # Initial status
                    self.results["clusters"][cluster_ip]["Create_VMs"][vm_info['name']] = "CAN'T VERIFY"

                    cluster_name = cluster_details["cluster_info"]["name"]
                    filter_criteria = f"cluster_name=={cluster_name};vm_name=={vm_info['name']}"

                    vms_response = vm_obj.list(filter=filter_criteria)
                    if len(vms_response) > 0:
                        self.results["clusters"][cluster_ip]["Create_VMs"][vm_info['name']] = "PASS"
                    else:
                        self.results["clusters"][cluster_ip]["Create_VMs"][vm_info['name']] = "FAIL"
            except Exception as e:
                self.logger.debug(e)
                self.logger.info(
                    f"Exception occurred during the verification of '{type(self).__name__}' for {cluster_ip}")
