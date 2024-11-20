from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v2.vm import VM

logger = get_logger(__name__)


class DeleteVmPe(ClusterScript):
    """
    Class that deletes NTP servers in PE
    """

    def __init__(self, data: Dict, **kwargs):
        super(DeleteVmPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs

        if self.parallel:
            self.set_current_thread_name(cluster_ip)
        pe_session = cluster_details["pe_session"]
        cluster_info = (
            f"{cluster_ip}/ {cluster_details['cluster_info']['name']}"
            if ("name" in cluster_details["cluster_info"])
            else f"{cluster_ip!r}"
        )
        try:
            if cluster_details.get("vms"):
                self.vms_list = cluster_details.get("vms")

                vm_op = VM(pe_session)

                existing_vms_list = vm_op.read()
                vm_name_uuid_dict = {vm["name"]: vm["uuid"] for vm in existing_vms_list}

                for vm in self.vms_list:
                    if vm["name"] not in vm_name_uuid_dict.keys():
                        self.logger.info(
                            f"VM {vm['name']} not present in {cluster_info!r}.. Skipping"
                        )
                        continue
                    self.logger.info(f"Deleting VM {vm['name']} in {cluster_info!r}")
                    response = vm_op.delete(endpoint=vm_name_uuid_dict[vm["name"]])

                    if response["task_uuid"]:
                        self.logger.info(
                            f"Deleting VM {vm['name']} successful in {cluster_info!r}"
                        )
                    else:
                        raise Exception(
                            f"Could not delete VM {vm['name']} successful in {cluster_info!r}"
                        )
        except Exception as e:
            self.exceptions.append(e)

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        try:
            if not cluster_details.get("vms"):
                return

            # Initial status
            self.results["clusters"][cluster_ip] = {"DeleteVMs": {}}

            pe_session = cluster_details["pe_session"]
            vm_op = VM(pe_session)

            existing_vms_name_list = [vm["name"] for vm in vm_op.read()]
            for vm in cluster_details["vms"]:
                # Initial status
                self.results["clusters"][cluster_ip]["DeleteVMs"][vm["name"]] = "CAN'T VERIFY"
                if vm not in existing_vms_name_list:
                    self.results["clusters"][cluster_ip]["DeleteVMs"][vm["name"]] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["DeleteVMs"][vm["name"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(
                f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}"
            )
