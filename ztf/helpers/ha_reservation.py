"""
HA Reservation Helper

Backport of the zero-touch-ee pe/update/ha_reservation.py helper into the v4
entity_handler interface. Sets the host-failure-tolerance reservation on the
PE cluster the domain's session is connected to, via the v0.8 REST API. No
v4 equivalent exists for cluster-local HA failover reservation settings.

API: GET/PUT api/nutanix/v0.8/ha
"""

from __future__ import annotations

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.rest_utils import RestAPIUtil
from ztf.utils.utils import get_logger

HA_V08_PATH = "api/nutanix/v0.8/ha"
CLUSTER_V2_PATH = "api/nutanix/v2/cluster"
HA_RESERVATION_EXT_ID = "ha_reservation"


class HaReservationHelper(PeEntityV1):
    """
    Helper for setting the HA failure-tolerance reservation on a PE cluster.

    There is exactly one HA reservation setting per PE cluster, and the
    domain-scoped ``session`` passed at construction already targets that
    cluster (see ``EntityHandler._build_rest_session``), so this helper
    operates directly on it -- no separate per-resource cluster IP or
    credential is needed. Skips single-node clusters (HA not supported).
    """

    def __init__(
        self,
        session: RestAPIUtil,
        proxy_cluster_uuid: str | None = None,
        logger=None,
        data: dict | None = None,
    ):
        self.resource_type = "/cluster"
        self.logger = logger if logger else get_logger(__name__)
        self.data = data or {}
        super().__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def _get_num_nodes(self) -> int | None:
        try:
            resp = self.session.get(CLUSTER_V2_PATH)
            if isinstance(resp, dict):
                return resp.get("numNodes", resp.get("num_nodes", 0))
        except Exception as e:
            self.logger.warning(f"Could not fetch cluster info: {e}")
        return 0

    def _read_ha(self) -> dict:
        return self.session.get(HA_V08_PATH)

    def _update_ha(self, num_host_failures: int) -> dict:
        payload = {"numHostFailuresToTolerate": num_host_failures}
        return self.session.put(HA_V08_PATH, data=payload)

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Set the HA failure-tolerance reservation on the PE cluster.

        Expected entity_data:
        {
            "num_host_failure_to_tolerate": 1
        }

        The PE API only requires ``numHostFailuresToTolerate`` in the PUT
        payload; there is no separate enable/disable flag. To disable HA
        reservation, set ``num_host_failure_to_tolerate`` to ``0`` and
        apply again (routed through ``update_entity``).

        :return: a fixed sentinel ext_id, since this setting is a
            singleton per cluster/domain.
        """
        num_failures = entity_data.get("num_host_failure_to_tolerate", 1)

        try:
            num_nodes = self._get_num_nodes()
            if num_nodes == 1:
                self.logger.warning(
                    "HA reservation not supported for single-node cluster. Skipping."
                )
                return HA_RESERVATION_EXT_ID

            current = self._read_ha()
            current_failures = (
                current.get("numHostFailuresToTolerate")
                if isinstance(current, dict)
                else None
            )

            if current_failures == num_failures:
                self.logger.info(
                    f"HA already set to numHostFailuresToTolerate={num_failures}. "
                    "Skipping."
                )
                return HA_RESERVATION_EXT_ID

            self.logger.info(
                f"Updating HA reservation: numHostFailuresToTolerate={num_failures}"
            )
            resp = self._update_ha(num_failures)

            if isinstance(resp, dict) and resp.get("taskUuid"):
                self.logger.info(f"HA update task submitted: {resp['taskUuid']}")

            self.logger.info("HA reservation updated")
            return HA_RESERVATION_EXT_ID

        except Exception as e:
            self.logger.error(f"Failed to update HA reservation: {e}")
            raise

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        return self.create_entity(entity_data)

    def delete_entity(self, ext_id: str) -> bool:
        raise NotImplementedError(
            "Delete operation is not supported for HA reservation"
        )

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        try:
            current = self._read_ha()
            if isinstance(current, dict):
                return [self._to_entity_data(current)]
            return []
        except Exception as e:
            self.logger.error(f"Failed to list HA status: {e}")
            return []

    @staticmethod
    def _to_entity_data(current: dict[str, Any]) -> dict[str, Any]:
        """Map a raw v0.8 HA response back to the snake_case keys
        ``create_entity`` accepts (see ``helper_schema`` in
        ``entity_map.py``), so state bodies read back via
        ``get_entity_by_ext_id``/``list_entities`` stay comparable to
        user config for drift detection.
        """
        return {
            "extId": HA_RESERVATION_EXT_ID,
            "num_host_failure_to_tolerate": current.get("numHostFailuresToTolerate"),
        }

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        try:
            current = self._read_ha()
            if isinstance(current, dict):
                entry = self._to_entity_data(current)
                return {k: v for k, v in entry.items() if k != "extId"}
            return None
        except Exception as e:
            self.logger.error(f"Failed to get HA status: {e}")
            return None
