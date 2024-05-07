from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.scripts.python.helpers.v3.service import Service
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DisableMicrosegmentation(Script):
    """
    Class that disables Microsegmentation
    """
    def __init__(self, data: Dict, **kwargs):
        self.task_uuid = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(DisableMicrosegmentation, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        try:
            service = Service(self.pc_session)
            status = service.get_microseg_status()

            if status == Service.DISABLED:
                self.logger.warning(f"SKIP: Microsegmentation is already disabled in {self.data['pc_ip']!r}")
                return

            self.logger.info(f"Disabling Microsegmentation in {self.data['pc_ip']!r}")
            response = service.disable_microseg()

            if response.get("task_uuid"):
                self.task_uuid = response.get("task_uuid")

            # Monitor the task
            if self.task_uuid:
                app_response, status = PcTaskMonitor(
                    self.pc_session, task_uuid_list=[self.task_uuid]
                ).monitor()

                if app_response:
                    self.exceptions.append(f"Disabling Microseg failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Disabling Microseg in PC didn't happen in the prescribed timeframe"
                    )
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        self.results["Disable_Microseg"] = "CAN'T VERIFY"

        service = Service(self.pc_session)
        status = service.get_microseg_status()

        if status == Service.DISABLED:
            self.results["Disable_Microseg"] = "PASS"
        else:
            self.results["Disable_Microseg"] = "FAIL"
