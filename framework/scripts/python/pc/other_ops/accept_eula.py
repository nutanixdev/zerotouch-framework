from typing import Dict
from framework.scripts.python.helpers.v1.eula import Eula
from framework.helpers.log_utils import get_logger
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class AcceptEulaPc(Script):
    """
    Accept Eula
    """
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(AcceptEulaPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def accept_eula(self, data: Dict):
        eula = Eula(self.pc_session)

        if eula.is_eula_accepted():
            self.logger.warning(f"Eula is already accepted for the PC {self.data['pc_ip']!r}")
            return
        response = eula.accept_eula(**data)

        if response.get("value"):
            self.logger.info(f"Accepted End-User License Agreement in the PC {self.data['pc_ip']!r}")
        else:
            raise Exception(f"Could not Accept End-User License Agreement in the PC {self.data['pc_ip']!r}."
                            f" Error: {response}")

    def execute(self):
        if "eula" in self.data:
            try:
                self.accept_eula(self.data["eula"])
            except Exception as e:
                self.exceptions.append(f"Accept_eula failed for the PC {self.data['pc_ip']!r} with the error: {e}")

    def verify(self):
        try:
            if "eula" not in self.data:
                return

            self.results = {
                "Accept_Eula": "CAN'T VERIFY"
            }

            # Check if Eula is accepted
            eula = Eula(self.pc_session)

            if eula.is_eula_accepted():
                self.results["Accept_Eula"] = "PASS"
            else:
                self.results["Accept_Eula"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for the PC "
                             f"{self.data['pc_ip']!r}")
