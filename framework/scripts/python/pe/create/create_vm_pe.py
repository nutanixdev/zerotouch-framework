import traceback
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.progress_monitor import TaskMonitor
from framework.scripts.python.helpers.v2.vm import VM
from framework.scripts.python.pe.cluster_script import ClusterScript

logger = get_logger(__name__)


class CreateVmPe(ClusterScript):
    """
    The Script to create VM in PE clusters
    """

    def __init__(self, data: Dict, **kwargs):
        super(CreateVmPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger
        self.task_uuid_list = []

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
            'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        try:
            if cluster_details.get("vms"):
                vm_op = VM(session=pe_session)
                vm_name_list = [vm["name"] for vm in vm_op.read()]

                for vm_to_create in cluster_details["vms"]:
                    try:
                        vm_name = vm_to_create['name']

                        if vm_name in vm_name_list:
                            self.logger.info(f"VM {vm_name!r} already exists in {cluster_info!r}. Skipping...")
                            continue

                        self.logger.info(f"Creating a new VM {vm_name!r} in {cluster_info!r}")
                        vm_payload, error = vm_op.get_spec(vm_to_create)
                        if error:
                            self.exceptions.append(f"Failed generating VM spec for {vm_name}: {error}")
                            continue
                        response = vm_op.create(data=vm_payload)

                        if response.get("task_uuid"):
                            self.logger.info(f"Submitted task {response['task_uuid']!r} for creation of VM {vm_name!r}")
                            self.task_uuid_list.append(response['task_uuid'])
                        else:
                            raise Exception(f"Could not create the VM {vm_name!r}. Error: {response}")
                    except Exception as e:
                        # traceback_str = ''.join(traceback.format_tb(e.__traceback__))
                        self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                               f"{cluster_info!r} with the error: {e}")

                # Monitor the tasks
                if self.task_uuid_list:
                    app_response, status = TaskMonitor(pe_session,
                                                       task_uuid_list=self.task_uuid_list).monitor()

                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append(f"Timed out. Creation of some or all VMs in {cluster_info!r} "
                                               f"didn't happen in the prescribed timeframe")
            else:
                self.logger.info(f"No VMs specified in {cluster_info!r}. Skipping...")
        except Exception as e:
            tb_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info!r} with the error: {e} \n {tb_str}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if network is created in PE
        try:
            if not cluster_details.get("vms"):
                return

            self.results["clusters"][cluster_ip] = {"Create_VM": {}}
            pe_session = cluster_details["pe_session"]

            vm_op = VM(pe_session)
            vm_list = []
            vm_name_list = []

            for vm in cluster_details.get("vms"):
                # Set default status
                self.results["clusters"][cluster_ip]["Create_VM"][vm["name"]] = "CAN'T VERIFY"

                vm_list = vm_list or vm_op.read()
                vm_name_list = vm_name_list or [vm["name"] for vm in vm_list if vm.get("name")]

                if vm["name"] in vm_name_list:
                    self.results["clusters"][cluster_ip]["Create_VM"][vm["name"]] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Create_VM"][vm["name"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.exception(f"Exception occurred during the verification of {type(self).__name__!r} "
                                  f"for {cluster_ip}: {e}")
