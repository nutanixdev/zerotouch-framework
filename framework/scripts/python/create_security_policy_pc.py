from helpers.log_utils import get_logger
from scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from scripts.python.helpers.v3.security_rule import SecurityPolicy
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateNetworkSecurityPolicy(Script):
    """
    Class that creates Address Groups
    """

    def __init__(self, data: dict):
        self.task_uuid_list = None
        self.data = data
        self.security_policies = self.data.get("security_policies")
        self.pc_session = self.data["pc_session"]
        super(CreateNetworkSecurityPolicy, self).__init__()

    def execute(self, **kwargs):
        try:
            security_policy = SecurityPolicy(self.pc_session)
            security_policy_list = security_policy.list(length=10000)
            security_policy_name_list = [sp.get("spec").get("name")
                                         for sp in security_policy_list if sp.get("spec", {}).get("name")]

            if not self.security_policies:
                logger.warning(f"No security_policies to create in {self.data['pc_ip']}. Skipping...")
                return

            sps_to_create = []
            for sg in self.security_policies:
                if sg["name"] in security_policy_name_list:
                    logger.warning(f"{sg['name']} already exists in {self.data['pc_ip']}!")
                    continue
                try:
                    sps_to_create.append(security_policy.create_security_policy_spec(sg))
                except Exception as e:
                    self.exceptions.append(f"Failed to create Security policy {sg['name']}: {e}")

            if not sps_to_create:
                logger.warning(f"No security_policies to create in {self.data['pc_ip']}. Skipping...")
                return

            logger.info(f"Batch create Security Policies in {self.data['pc_ip']}")
            self.task_uuid_list = security_policy.batch_op.batch_create(request_payload_list=sps_to_create)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if self.task_uuid_list:
            app_response, status = PcTaskMonitor(self.pc_session,
                                                 task_uuid_list=self.task_uuid_list).monitor()

            if app_response:
                self.exceptions.append(f"Some tasks have failed. {app_response}")

            if not status:
                self.exceptions.append("Timed out. Creation of Security policies in PC didn't happen in the"
                                       " prescribed timeframe")
