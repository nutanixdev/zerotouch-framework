from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.v3.cloud_trust import CloudTrust
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DisconnectAz(Script):
    """
    Class that deletes AZs from PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(DisconnectAz, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        try:
            cloud_trust = CloudTrust(self.pc_session)
            if not self.data.get("remote_azs"):
                self.logger.warning(f"Skipping deletion of AZ in {self.data['pc_ip']!r}")
                return

            current_az_list = cloud_trust.list()


            az_name_uuid_map = {
                az.get("spec", {}).get("resources", {}).get("url"): az.get("metadata", {}).get("uuid")
                for az in current_az_list
            }
            
            az_uuid_list = []
            for az_ip in self.data["remote_azs"]:

                if az_ip not in az_name_uuid_map:
                    self.logger.warning(f"{az_ip!r} AZ is not present in {self.data['pc_ip']}!")
                    continue

                try:
                    self.logger.info(f"Deleting AZ {az_ip!r} in {self.data['pc_ip']}")
                    az_uuid_list.append(az_name_uuid_map[az_ip])
                except Exception as e:
                    self.exceptions.append(f"Failed to delete remote AZ '{az_ip}': {e}")

            if az_uuid_list:
                self.logger.info(f"Trigger batch delete API for AZs creation in {self.data['pc_ip']}")
                self.task_uuid_list = cloud_trust.batch_op.batch_delete(entity_list=az_uuid_list)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session, task_uuid_list=self.task_uuid_list
                ).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Deletion of AZs in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.data.get("remote_azs"):
            return

        # Initial status
        self.results["Delete_AZ"] = {}

        cloud_trust = CloudTrust(self.pc_session)
        current_az_list = cloud_trust.list()
        current_az_url_list = [az.get("spec", {}).get("url") for az in current_az_list]

        for az in self.data["remote_azs"]:
            # Initial status
            self.results["Delete_AZ"][az] = "CAN'T VERIFY"

            if az not in current_az_url_list:
                self.results["Delete_AZ"][az] = "PASS"
            else:
                self.results["Delete_AZ"][az] = "FAIL"
