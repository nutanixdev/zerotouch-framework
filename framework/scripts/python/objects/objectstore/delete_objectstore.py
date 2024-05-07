from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.objectstore_monitor import ObjectstoreMonitor
from framework.scripts.python.helpers.objects.objectstore import ObjectStore
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteObjectStore(Script):
    """
    Class that deletes Objectstores
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.object_stores_to_delete = self.data.get("objectstores") or self.data.get("objects", {}).get("objectstores", [])
        super(DeleteObjectStore, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        try:
            os = ObjectStore(self.pc_session)
            
            os_name_uuid_dict = {
                object_store.get('name'): object_store.get('uuid')
                for object_store in os.list() if object_store.get('name')
            }

            for object_store_to_delete in self.object_stores_to_delete:
                if object_store_to_delete["name"] not in os_name_uuid_dict.keys():
                    self.logger.warning(
                        f"SKIP: Objectstore with name {object_store_to_delete['name']} is not present in {self.data['pc_ip']!r}"
                    )
                    continue
                try:
                    os.delete(endpoint=os_name_uuid_dict[object_store_to_delete['name']])
                except Exception as e:
                    self.exceptions.append(f"Failed to delete Objectstore with name {object_store_to_delete['name']}: {e}")
                    continue
                
                _, status = ObjectstoreMonitor(self.pc_session, os_name=object_store_to_delete["name"]).monitor()
                if not status:
                    self.exceptions.append(
                        "Timed out. Deletion of Objectstore in PC didn't happen in the prescribed timeframe"
                    )
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.object_stores_to_delete:
            return

        # Initial status
        self.results["Delete_Objectstores"] = {}

        os = ObjectStore(self.pc_session)
        os_list = []
        os_name_state_map = {}

        for object_store_to_delete in self.object_stores_to_delete:
            # Initial status

            os_list = os_list or os.list()
            os_name_state_map = os_name_state_map or {
                object_store.get('name'): object_store.get('state') for object_store in os_list
            }

            if (object_store_to_delete["name"] not in os_name_state_map):
                self.results["Delete_Objectstores"][object_store_to_delete["name"]] = "PASS"
            else:
                self.results["Delete_Objectstores"][object_store_to_delete["name"]] = "FAIL"
