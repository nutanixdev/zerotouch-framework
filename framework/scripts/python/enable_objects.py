import sys
from typing import Dict
from framework.helpers.log_utils import get_logger
from .helpers.state_monitor.objects_enabled_monitor import ObjectsEnabledMonitor
from .helpers.v3.service import Service
from .script import Script

logger = get_logger(__name__)


class EnableObjects(Script):
    """
    Class that enables Objects/ OSS
    """
    def __init__(self, data: Dict, **kwargs):
        self.task_uuid = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(EnableObjects, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            service = Service(self.pc_session)
            status = service.get_oss_status()

            if status in [Service.ENABLED, Service.ENABLING]:
                self.logger.warning(f"SKIP: Objects/ OSS service is already enabled in '{self.data['pc_ip']}'")
                return

            self.logger.info(f"Enabling Objects/ OSS service in '{self.data['pc_ip']}'")
            response = service.enable_oss()

            if response.get("task_uuid"):
                self.task_uuid = response.get("task_uuid")

            # Monitor the task
            if self.task_uuid:
                _, status = ObjectsEnabledMonitor(self.pc_session).monitor()
                if not status:
                    self.exceptions.append(
                        "Timed out. Objects/ OSS in PC didn't happen in the prescribed timeframe")
                    sys.exit(1)
                else:
                    self.logger.info(f"Enabled Objects/ OSS service in the PC '{self.data['pc_ip']}'")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        self.results["Enable_Objects"] = "CAN'T VERIFY"

        service = Service(self.pc_session)
        status = service.get_oss_status()

        if status in [Service.ENABLED, Service.ENABLING]:
            self.results["Enable_Objects"] = "PASS"
        else:
            self.results["Enable_Objects"] = "FAIL"
