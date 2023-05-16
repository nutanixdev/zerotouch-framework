from helpers.log_utils import get_logger
from scripts.python.helpers.v3.address_group import AddressGroup
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateAddressGroups(Script):
    """
    Class that creates Address Groups
    """
    def __init__(self, data: dict):
        self.task_uuid_list = None
        self.data = data
        self.address_groups = self.data.get("address_groups")
        self.pc_session = self.data["pc_session"]
        super(CreateAddressGroups, self).__init__()

    def execute(self, **kwargs):
        try:
            address_group = AddressGroup(self.pc_session)
            address_group_list = address_group.list()
            address_group_name_list = [ag.get("address_group", {}).get("name")
                                       for ag in address_group_list if ag.get("address_group", {}).get("name")]

            if not self.address_groups:
                logger.warning(f"No address_groups to create in {self.data['pc_ip']}. Skipping...")
                return

            ags_to_create = []
            for ag in self.address_groups:
                if ag["name"] in address_group_name_list:
                    logger.warning(f"{ag['name']} already exists in {self.data['pc_ip']}!")
                    continue
                try:
                    ags_to_create.append(address_group.create_address_group_spec(ag))
                except Exception as e:
                    self.exceptions.append(f"Failed to create address_group {ag['name']}: {e}")

            if not ags_to_create:
                logger.warning(f"No address_groups to create in {self.data['pc_ip']}. Skipping...")
                return

            logger.info(f"Batch create Address groups in {self.data['pc_ip']}")
            address_group.batch_op.batch_create(request_payload_list=ags_to_create)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # todo verify
        pass
