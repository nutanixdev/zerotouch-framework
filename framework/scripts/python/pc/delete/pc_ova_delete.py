from typing import Dict

from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v3.ova import Ova
from framework.scripts.python.script import Script
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor

logger = get_logger(__name__)


class PcOVADelete(Script):
    """
    Class to delete OVAs to PC clusters
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = data["pc_session"]
        super(PcOVADelete, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        try:
            if self.data.get('ovas'):
                ova_config_list = self.data.get('ovas')
                ova_delete = Ova(session=self.pc_session)

                # Get Exisiting OVA name and uuid from PC
                existing_ova_uuid_map = {
                    ova.get('info', {}).get('name'): ova.get('metadata').get('uuid') for ova in ova_delete.list()
                }

                ova_to_delete_uuid_lists = []
                # Check if given OVAs exists in PC & remove if it doesn't exist
                for ova_config in ova_config_list:
                    if ova_config["name"] not in existing_ova_uuid_map.keys():
                        logger.warning(f"OVA {ova_config['name']} doesn't exist")
                        continue
                    ova_to_delete_uuid_lists.append(existing_ova_uuid_map[ova_config["name"]])

                # Delete OVAs to PC clusters
                if not ova_to_delete_uuid_lists:
                    self.logger.warning(f"Provided OVAs are not present in {self.data['pc_ip']}")
                    return
                
                logger.info(f"Trigger batch delete API for OVAs in {self.data['pc_ip']!r}")
                task_uuid_list = ova_delete.batch_op.batch_delete(ova_to_delete_uuid_lists)
                
                #Monitor Tasks
                if task_uuid_list:
                    app_response, status = PcTaskMonitor(
                        self.pc_session, task_uuid_list=task_uuid_list
                    ).monitor()

                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append(
                            "Timed out. OVA delete didn't happen in the prescribed timeframe"
                        )

        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        """
        Verify if the OVAs are deleted in PC
        """
        try:
            if not self.data.get("ovas"):
                return
            self.results["OVA_Delete"] = {}

            ova_upload = Ova(session=self.pc_session)
            # Get Exisiting OVA list from PC
            existing_ova_list = [ova.get('info').get('name') for ova in ova_upload.list()]
            # Check if the OVA(s) are deleted in PC
            for ova_config in self.data.get("ovas"):
                if ova_config["name"] not in existing_ova_list:
                    self.results["OVA_Delete"][ova_config["name"]] = "PASS"
                else:
                    self.results["OVA_Delete"][ova_config["name"]] = "FAIL"
        except Exception as e:
            self.logger.error(e)
