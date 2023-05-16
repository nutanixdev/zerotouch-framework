from helpers.log_utils import get_logger
from scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from scripts.python.helpers.v3.service import Service
from scripts.python.script import Script

logger = get_logger(__name__)


class EnableMicroseg(Script):
    """
    Class that enables microseg/ Flow
    """
    def __init__(self, data: dict):
        self.task_uuid = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(EnableMicroseg, self).__init__()

    def execute(self, **kwargs):
        try:
            service = Service(self.pc_session)
            status = service.get_microseg_status()

            if status in ["ENABLED", "ENABLING"]:
                logger.warning(f"SKIP: microseg/ flow service is already enabled {self.data['pc_ip']}")
                return

            logger.info(f"Enabling Microseg/ Flow service {self.data['pc_ip']}")
            response = service.enable_microseg()

            if response.get("task_uuid"):
                self.task_uuid = response.get("task_uuid")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if self.task_uuid:
            app_response, status = PcTaskMonitor(self.pc_session,
                                                 task_uuid_list=[self.task_uuid]).monitor()

            if not status:
                self.exceptions.append("Timed out. Enabling Microseg/ Flow in PC didn't happen in the prescribed timeframe")
