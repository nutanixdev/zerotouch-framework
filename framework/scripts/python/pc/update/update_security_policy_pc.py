from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript


logger = get_logger(__name__)


class UpdateNetworkSecurityPolicy(PcScript):
    """
    Class that modifies Security policies using name as the unique identifier
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.security_policies = self.data.get("security_policies")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(UpdateNetworkSecurityPolicy, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.security_policy_util = self.import_helpers_with_version_handling("SecurityPolicy")

    def execute(self):
        try:
            if not self.security_policies:
                self.logger.warning(f"No security_policies provided to modify in {self.data['pc_ip']!r}")
                return

            security_policy_name_uuid_dict = self.security_policy_util.get_name_uuid_dict()
            sps_to_update = []
            for sp in self.security_policies:
                if sp["name"] not in security_policy_name_uuid_dict.keys():
                    self.logger.warning(f"Security Policy with name {sp['name']} doesn't exist in {self.data['pc_ip']!r}!")
                    continue
                try:
                    sec_pol_obj = self.security_policy_util.get_by_ext_id(security_policy_name_uuid_dict[sp["name"]])
                    sps_to_update.append(self.security_policy_util.update_security_policy_spec(sp, sec_pol_obj.data))
                except Exception as e:
                    self.exceptions.append(f"Failed to Update Security policy {sp['name']}: {e}")

            if not sps_to_update:
                self.logger.warning(f"No security_policies to update in {self.data['pc_ip']!r}. Skipping...")
                return
            self.logger.info(f"Trigger batch update API for Security Policies in {self.data['pc_ip']!r}")

            
            self.task_uuid_list = self.security_policy_util.batch_op.batch_update(entity_update_list=sps_to_update)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Updation of Security policies in PC didn't happen in the"
                                           " prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.security_policies:
            return

        # Initial status
        self.results["Update_Security_policies"] = {}
        security_policy_name_list = []

        for sg in self.security_policies:
            # Initial status
            self.results["Update_Security_policies"][sg['name']] = "CAN'T VERIFY"
            security_policy_name_list = security_policy_name_list or self.security_policy_util.get_name_list()
            name = sg["new_name"] if "new_name" in sg else sg["name"]
            if name in security_policy_name_list:
                self.results["Update_Security_policies"][sg['name']] = "PASS"
            else:
                self.results["Update_Security_policies"][sg['name']] = "FAIL"
