from typing import Dict
from framework.scripts.python.helpers.v1.pulse import Pulse
from framework.helpers.log_utils import get_logger
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class UpdatePulsePc(Script):
    """
    Update Pulse
    """
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(UpdatePulsePc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def update_pulse(self, enable_pulse: bool):
        pulse = Pulse(session=self.pc_session)

        # get current status
        current_status = pulse.read().get("enable")
        if current_status == enable_pulse:
            self.logger.warning(f"Pulse is already '{enable_pulse}' in the PC {self.data['pc_ip']!r}")

        pulse.update_pulse(enable=enable_pulse)

    def execute(self):
        if "enable_pulse" in self.data:
            try:
                self.update_pulse(self.data.get("enable_pulse", False))
            except Exception as e:
                self.exceptions.append(f"Update_pulse failed for the PC {self.data['pc_ip']!r} with the error: {e}")

    def verify(self):
        try:
            if "enable_pulse" not in self.data:
                return
            self.results = {
                "Update_Pulse": "CAN'T VERIFY"
            }

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
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for the PC "
                             f"{self.data['pc_ip']!r}")
