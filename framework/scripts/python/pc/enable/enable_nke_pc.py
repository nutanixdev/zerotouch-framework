from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v1.genesis import Genesis
from framework.scripts.python.helpers.state_monitor.karbon_enabled_monitor import KarbonEnabledMonitor
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class EnableNke(Script):
    """
    Class that enables Karbon/ NKE
    """
    def __init__(self, data: Dict, **kwargs):
        self.status = False
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(EnableNke, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            genesis = Genesis(self.pc_session)
            status, _ = genesis.is_karbon_enabled()

            if status:
                self.logger.warning(f"SKIP: NKE/ Karbon service is already enabled {self.data['pc_ip']!r}")
                return

            self.logger.info(f"Enabling NKE/ Karbon service {self.data['pc_ip']!r}")
            self.status, _ = genesis.enable_karbon()

            # Monitor the task
            if self.status:
                _, status = KarbonEnabledMonitor(self.pc_session).monitor()

                if not status:
                    self.exceptions.append(
                        "Timed out. Enabling NKE/ Karbon service in PC didn't happen in the prescribed "
                        "timeframe")
                else:
                    self.logger.info(f"Enabled NKE/ Karbon service in the PC {self.data['pc_ip']!r}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        self.results["Enable_NKE"] = "CAN'T VERIFY"

        genesis = Genesis(self.pc_session)
        status, _ = genesis.is_karbon_enabled()

        if status:
            self.results["Enable_NKE"] = "PASS"
        else:
            self.results["Enable_NKE"] = "FAIL"
