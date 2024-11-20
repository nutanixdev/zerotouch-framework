from typing import Dict

from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v3.ova import Ova
from framework.scripts.python.script import Script
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor

logger = get_logger(__name__)


class PcOVAUpload(Script):
    """
    Class to upload OVAs to PC clusters
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = data["pc_session"]
        super(PcOVAUpload, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if self.data.get("ovas"):
                ova_config_list = self.data.get("ovas")
                ova_upload = Ova(session=self.pc_session)

                # Get Existing OVA list from PC
                existing_ova_list = [ova["info"]["name"] for ova in ova_upload.list()]
                # Check if OVA already exists in PC & remove the config from config list
                for ova_config in ova_config_list:
                    if ova_config["name"] in existing_ova_list:
                        ova_config_list.remove(ova_config)
                        logger.warning(f"OVA {ova_config['name']} already exists")

                # Upload OVAs to PC clusters
                task_uuid_list = ova_upload.url_upload(ova_config_list)
                if task_uuid_list:
                    pc_task_monitor = PcTaskMonitor(self.pc_session,
                                                    task_uuid_list=task_uuid_list)
                    pc_task_monitor.DEFAULT_CHECK_INTERVAL_IN_SEC = 10
                    pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC = 600
                    app_response, status = pc_task_monitor.monitor()

                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append("Timed out. OVA upload didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        """
        Verify if the OVAs are present in PC
        """
        try:
            if not self.data.get("ovas"):
                return
            self.results["OVA_Upload"] = {}

            ova_upload = Ova(session=self.pc_session)
            # Get Existing OVA list from PC
            existing_ova_list = [ova["info"]["name"] for ova in ova_upload.list()]

            # Check if the OVA(s) are present in PC
            for ova_config in self.data.get("ovas"):
                if ova_config["name"] in existing_ova_list:
                    self.results["OVA_Upload"][ova_config["name"]] = "PASS"
                    self.logger.info("OVA '{}' uploaded successfully".format(ova_config["name"]))
                else:
                    self.results["OVA_Upload"][ova_config["name"]] = "FAIL"
        except Exception as e:
            self.logger.error(e)
