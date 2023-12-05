from typing import Dict
from framework.helpers.log_utils import get_logger
from .helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from .helpers.v3.service import Service
from .script import Script

logger = get_logger(__name__)


class EnableDR(Script):
    """
    Class that enables Leap/ DR
    """
    def __init__(self, data: Dict, **kwargs):
        self.task_uuid = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(EnableDR, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            service = Service(self.pc_session)
            status = service.get_dr_status()

            if status in [Service.ENABLED, Service.ENABLING]:
                self.logger.warning(f"SKIP: Leap/ DR service is already enabled in '{self.data['pc_ip']}'")
                return

            self.logger.info(f"Enabling Leap/ DR service in '{self.data['pc_ip']}'")
            response = service.enable_leap()

            if response.get("task_uuid"):
                self.task_uuid = response.get("task_uuid")

            # Monitor the task
            if self.task_uuid:
                app_response, status = PcTaskMonitor(self.pc_session,
                                                     task_uuid_list=[self.task_uuid]).monitor()

                if app_response:
                    self.exceptions.append(f"Enabling DR failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Enabling Leap/ DR in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        self.results["Enable_DR"] = "CAN'T VERIFY"

        service = Service(self.pc_session)
        status = service.get_dr_status()

        if status in [Service.ENABLED, Service.ENABLING]:
            self.results["Enable_DR"] = "PASS"
        else:
            self.results["Enable_DR"] = "FAIL"
