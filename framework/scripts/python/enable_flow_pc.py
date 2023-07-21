from helpers.log_utils import get_logger
from scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from scripts.python.helpers.v3.service import Service
from scripts.python.script import Script

logger = get_logger(__name__)


class EnableFlow(Script):
    """
    Class that enables microseg/ Flow
    """
    def __init__(self, data: dict, **kwargs):
        self.task_uuid = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(EnableFlow, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            service = Service(self.pc_session)
            status = service.get_microseg_status()

            if status in ["ENABLED", "ENABLING"]:
                self.logger.warning(f"SKIP: Microseg/ flow service is already enabled '{self.data['pc_ip']}'")
                return

            self.logger.info(f"Enabling Microseg/ Flow service '{self.data['pc_ip']}'")
            response = service.enable_microseg()

            if response.get("task_uuid"):
                self.task_uuid = response.get("task_uuid")

            # Monitor the task
            if self.task_uuid:
                app_response, status = PcTaskMonitor(self.pc_session,
                                                     task_uuid_list=[self.task_uuid]).monitor()

                if app_response:
                    self.exceptions.append(f"Enabling Flow failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Enabling Microseg/ Flow in PC didn't happen in the prescribed "
                                           "timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        self.results["Enable_Flow"] = "CAN'T VERIFY"

        service = Service(self.pc_session)
        status = service.get_microseg_status()

        if status in ["ENABLED", "ENABLING"]:
            self.results["Enable_Flow"] = "PASS"
        else:
            self.results["Enable_Flow"] = "FAIL"
