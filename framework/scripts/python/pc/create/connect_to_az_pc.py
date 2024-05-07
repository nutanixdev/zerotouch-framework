from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.scripts.python.helpers.v3.cloud_trust import CloudTrust
from framework.scripts.python.script import Script
from framework.helpers.helper_functions import read_creds

logger = get_logger(__name__)


class ConnectToAz(Script):
    """
    Class that connects to AZs
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(ConnectToAz, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            cloud_trust = CloudTrust(self.pc_session)

            if not self.data.get("remote_azs"):
                self.logger.warning(f"Skipping creation of AZ in {self.data['pc_ip']!r}")
                return

            current_az_list = cloud_trust.list()
            current_az_list = [az.get("spec", {}).get("resources", {}).get("url")
                               for az in current_az_list if az.get("spec", {}).get("resources", {}).get("url")]

            az_list = []
            for az, details in self.data["remote_azs"].items():
                remote_pc_ip = az
                remote_pc_credential = details.get("pc_credential")
                # get credentials from the payload
                try:
                    remote_pc_username, remote_pc_password = read_creds(data=self.data, credential=remote_pc_credential)
                except Exception as e:
                    self.exceptions.append(e)
                    continue

                cloud_type = details.get("cloud_type", "ONPREM_CLOUD")

                if remote_pc_ip in current_az_list:
                    self.logger.warning(f"{remote_pc_ip!r} AZ is already added in {self.data['pc_ip']!r}!")
                    continue

                try:
                    self.logger.info(f"Creating AZ {remote_pc_ip!r} in {self.data['pc_ip']!r}")
                    spec = CloudTrust.get_payload(cloud_type, remote_pc_ip, remote_pc_username, remote_pc_password)
                    az_list.append(spec)
                except Exception as e:
                    self.exceptions.append(f"Failed to add remote AZ {remote_pc_ip!r}: {e}")

            if az_list:
                self.logger.info(f"Trigger batch create API for AZs creation in {self.data['pc_ip']!r}")
                self.task_uuid_list = cloud_trust.batch_op.batch_create(request_payload_list=az_list)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(self.pc_session,
                                                     task_uuid_list=self.task_uuid_list).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Creation of AZs in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.data.get("remote_azs"):
            return

        # Initial status
        self.results["Create_AZ"] = {}

        # In batch requests verification gets really difficult by just monitoring batch response,
        # so just checking the AZ list and verifying the creation
        cloud_trust = CloudTrust(self.pc_session)
        current_az_list = []
        current_az_url_list = []

        for az in self.data["remote_azs"].keys():
            # Initial status
            self.results["Create_AZ"][az] = "CAN'T VERIFY"

            remote_pc_ip = az
            current_az_list = current_az_list or cloud_trust.list()
            current_az_url_list = current_az_url_list or [az.get("spec", {}).get("resources", {}).get("url")
                                                          for az in current_az_list if
                                                          az.get("spec", {}).get("resources", {}).get("url")]
            if remote_pc_ip in current_az_url_list:
                self.results["Create_AZ"][az] = "PASS"
            else:
                self.results["Create_AZ"][az] = "FAIL"
