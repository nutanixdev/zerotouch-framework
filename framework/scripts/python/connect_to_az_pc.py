from helpers.log_utils import get_logger
from scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from scripts.python.helpers.v3.cloud_trust import CloudTrust
from scripts.python.script import Script

logger = get_logger(__name__)


class ConnectToAz(Script):
    """
    Class that connects to AZs
    """

    def __init__(self, data: dict):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(ConnectToAz, self).__init__()

    def execute(self, **kwargs):
        try:
            cloud_trust = CloudTrust(self.pc_session)

            if not self.data.get("remote_azs"):
                logger.warning(f"Skipping creation of AZ in {self.data['pc_ip']}")
                return

            current_az_list = cloud_trust.list()
            current_az_list = [az.get("spec", {}).get("resources", {}).get("url")
                               for az in current_az_list if az.get("spec", {}).get("resources", {}).get("url")]

            az_list = []
            for az, details in self.data["remote_azs"].items():
                remote_pc_ip = az
                remote_pc_username = details["username"]
                remote_pc_password = details["password"]
                cloud_type = details.get("cloud_type", "ONPREM_CLOUD")

                if remote_pc_ip in current_az_list:
                    logger.warning(f"{remote_pc_ip} AZ is already added in {self.data['pc_ip']}!")
                    return

                try:
                    spec = CloudTrust.get_payload(cloud_type, remote_pc_ip, remote_pc_username, remote_pc_password)
                    az_list.append(spec)
                except Exception as e:
                    self.exceptions.append(f"Failed to add remote AZ {remote_pc_ip}: {e}")

            logger.info(f"Batch create AZs creation in {self.data['pc_ip']}")
            self.task_uuid_list = cloud_trust.batch_op.batch_create(request_payload_list=az_list)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if self.task_uuid_list:
            app_response, status = PcTaskMonitor(self.pc_session,
                                                 task_uuid_list=self.task_uuid_list).monitor()

            if app_response:
                self.pass_rate.append(f"Some tasks have failed. {app_response}")

            if not status:
                self.pass_rate.append("Timed out. Creation of AZs in PC didn't happen in the prescribed timeframe")
