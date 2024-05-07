from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v0_8 import PeEntityV0_8


class HA(PeEntityV0_8):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/ha"
        super(HA, self).__init__(session=session)

    def update_ha_reservation(self, enable_failover: bool = True, num_host_failure_to_tolerate: int = 1):
        """Enable HA reservation

        Args:
            enable_failover (bool, optional): Enable or Disable Pulse in PE. Defaults to True.
            num_host_failure_to_tolerate (int, optional): Number of host failures to tolerate. Defaults to 1.
        """
        data = {
            "enableFailover": enable_failover,
            "numHostFailuresToTolerate": num_host_failure_to_tolerate
        }

        return self.update(data=data)
