from helpers.log_utils import get_logger
from scripts.python.helpers.v3.service_group import ServiceGroup
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateServiceGroups(Script):
    """
    Class that creates Address Groups
    """

    def __init__(self, data: dict):
        self.task_uuid_list = None
        self.data = data
        self.service_groups = self.data.get("service_groups")
        self.pc_session = self.data["pc_session"]
        super(CreateServiceGroups, self).__init__()

    def execute(self, **kwargs):
        try:
            service_group = ServiceGroup(self.pc_session)
            service_group_list = service_group.list(length=10000)
            service_group_name_list = [ag.get("service_group", {}).get("name")
                                       for ag in service_group_list if ag.get("service_group", {}).get("name")]

            if not self.service_groups:
                logger.warning(f"No service_groups to create in {self.data['pc_ip']}. Skipping...")
                return

            sgs_to_create = []
            for sg in self.service_groups:
                if sg["name"] in service_group_name_list:
                    logger.warning(f"{sg['name']} already exists!")
                    continue
                try:
                    sgs_to_create.append(service_group.create_service_group_spec(sg))
                except Exception as e:
                    self.exceptions.append(f"Failed to create Security policy {sg['name']}: {e}")

            if not sgs_to_create:
                logger.warning(f"No service_groups to create in {self.data['pc_ip']}. Skipping...")
                return

            logger.info(f"Batch create service groups in {self.data['pc_ip']}")
            service_group.batch_op.batch_create(request_payload_list=sgs_to_create)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # todo verify
        pass
