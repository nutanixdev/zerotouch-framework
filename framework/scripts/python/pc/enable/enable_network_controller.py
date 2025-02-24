import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript
from framework.scripts.python.helpers.v4.network_controller import NetworkController

logger = get_logger(__name__)


class EnableNetworkController(PcScript):
    """
    Class that enables Network Controller in PC
    """
    def __init__(self, data: Dict, **kwargs):
        self.response = None
        self.task_uuid_list = []
        self.data = data
        self.pc_session = data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(EnableNetworkController, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.network_controller_helper = self.import_helpers_with_version_handling("NetworkController")

    def execute(self, **kwargs):
        try:
            if self.network_controller_helper.get_network_controller_status():
                self.logger.warning(f"SKIP: Network Controller is already enabled in {self.data['pc_ip']!r}")
                return
            
            self.logger.info(f"Creating Network Controller in {self.data['pc_ip']!r}")
            response = self.network_controller_helper.enable_network_controller()
            
            self.task_uuid_list = [response.data.ext_id]
            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Enable Network Controller in PC didn't happen in the"
                                           " prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        self.results["EnableNetworkController"] = {}
        if self.network_controller_helper.get_network_controller_status():
            self.results["EnableNetworkController"]["status"] = "PASS"
        else:
            self.results["EnableNetworkController"]["status"] = "FAIL"
