import time
from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from .helpers.v1.utils_manager import UtilsManager
from .helpers.v1.eula import Eula
from .helpers.v1.pulse import Pulse
from .helpers.v2.cluster import Cluster as PcCluster
from framework.helpers.log_utils import get_logger
from .script import Script

logger = get_logger(__name__)


class InitialPcConfig(Script):
    """
    Change default PC password
    Accept Eula
    Enable Pulse
    """
    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.default_pc_session = RestAPIUtil(self.data['pc_ip'], user=self.DEFAULT_USERNAME,
                                              pwd=self.DEFAULT_SYSTEM_PASSWORD,
                                              port="9440", secured=True)
        self.pc_session = RestAPIUtil(self.data['pc_ip'], user=self.DEFAULT_USERNAME,
                                      pwd=self.data.get('admin_pc_password') or self.data.get("pc_password"),
                                      port="9440", secured=True)
        super(InitialPcConfig, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def change_default_password(self, new_pc_password: str):
        default_system_password = UtilsManager(self.default_pc_session)
        response = default_system_password.change_default_system_password(new_pc_password)

        if response["value"]:
            self.logger.info(f"Default System password updated with new password the PC {self.data['pc_ip']}")
        else:
            raise Exception(f"Could not change the PC password {self.data['pc_ip']}. Error: {response}")
        # Waiting for password sync
        time.sleep(30)

    def accept_eula(self, data: Dict):
        eula = Eula(self.pc_session)

        if eula.is_eula_accepted():
            self.logger.warning(f"Eula is already accepted for the PC {self.data['pc_ip']}")
            return
        response = eula.accept_eula(**data)

        if response["value"]:
            self.logger.info(f"Accepted End-User License Agreement in the PC {self.data['pc_ip']}")
        else:
            raise Exception(f"Could not Accept End-User License Agreement in the PC {self.data['pc_ip']}."
                            f" Error: {response}")

    def update_pulse(self, enable_pulse: bool):
        pulse = Pulse(session=self.pc_session)

        # get current status
        current_status = pulse.read().get("enable")
        if current_status == enable_pulse:
            self.logger.warning(f"Pulse is already '{enable_pulse}' in the PC {self.data['pc_ip']}")

        pulse.update_pulse(enable=enable_pulse)

    def execute(self):
        new_pc_password = self.data.get('new_admin_pc_password') or self.data.get("pc_password")
        if new_pc_password == self.DEFAULT_SYSTEM_PASSWORD:
            self.logger.error(f"New Password specified is same as default password for the PC ...")
            return

        try:
            self.change_default_password(new_pc_password)
        except Exception as e:
            self.exceptions.append(
                f"Change_default_password failed for the PC {self.data['pc_ip']} with the error: {e}")
        try:
            self.accept_eula(self.data.get("eula"))
        except Exception as e:
            self.exceptions.append(f"Accept_eula failed for the PC {self.data['pc_ip']} with the error: {e}")
        try:
            self.update_pulse(self.data.get("enable_pulse", False))
        except Exception as e:
            self.exceptions.append(f"Update_pulse failed for the PC {self.data['pc_ip']} with the error: {e}")

    def verify(self):
        try:
            self.results = {
                "Change_Default_password": "CAN'T VERIFY",
                "Accept_Eula": "CAN'T VERIFY",
                "Update_Pulse": "CAN'T VERIFY"
            }

            # Check if password is changed
            try:
                endpoint = "cluster"
                cluster_obj = PcCluster(self.default_pc_session)
                cluster_obj.read(endpoint=endpoint)
            except Exception:
                # if it fails, i.e default password doesn't work, password is changed
                self.results["Change_Default_password"] = "PASS"

            # Check if Eula is accepted
            eula = Eula(self.pc_session)

            if eula.is_eula_accepted():
                self.results["Accept_Eula"] = "PASS"
            else:
                self.results["Accept_Eula"] = "FAIL"

            if self.data.get("enable_pulse", None) is not None:
                # Check if Pulse is updated
                pulse = Pulse(session=self.pc_session)
                # get current status
                current_status = pulse.read().get("enable")
                if current_status == self.data.get("enable_pulse"):
                    self.results["Update_Pulse"] = "PASS"
                else:
                    self.results["Update_Pulse"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}' for the PC "
                             f"{self.data['pc_ip']}")
