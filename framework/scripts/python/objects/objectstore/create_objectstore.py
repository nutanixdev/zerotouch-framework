from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.objectstore_monitor import ObjectstoreMonitor
from framework.scripts.python.helpers.objects.objectstore import ObjectStore
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateObjectStore(Script):
    """
    Class that creates Objectstores
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.object_stores_to_create = self.data.get("objectstores") or self.data.get("objects", {}). \
            get("objectstores", [])
        super(CreateObjectStore, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            os = ObjectStore(self.pc_session)
            os_list = [object_store.get('name') for object_store in os.list()]

            for object_store_to_create in self.object_stores_to_create:
                if object_store_to_create["name"] in os_list:
                    self.logger.warning(f"SKIP: Objectstore with name {object_store_to_create['name']} is "
                                        f"already present in {self.data['pc_ip']!r}")
                    continue

                try:
                    os.create(**object_store_to_create)
                except Exception as e:
                    self.exceptions.append(f"Failed to create Objectstore with name {object_store_to_create['name']}: "
                                           f"{e}")
                    continue

                _, status = ObjectstoreMonitor(self.pc_session, os_name=object_store_to_create["name"]).monitor()

                if not status:
                    self.exceptions.append(
                        "Timed out. Creation of Objectstore in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.object_stores_to_create:
            return

        # Initial status
        self.results["Create_Objectstores"] = {}

        os = ObjectStore(self.pc_session)
        os_list = []
        os_name_state_map = {}

        for object_store_to_create in self.object_stores_to_create:
            # Initial status

            os_list = os_list or os.list()
            os_name_state_map = os_name_state_map or {object_store.get('name'): object_store.get('state') for
                                                      object_store in os_list}

            if (object_store_to_create["name"] in os_name_state_map) and \
                    os_name_state_map.get(object_store_to_create["name"]) == os.COMPLETE:
                self.results["Create_Objectstores"][object_store_to_create["name"]] = "PASS"
            else:
                self.results["Create_Objectstores"][object_store_to_create["name"]] = "FAIL"
