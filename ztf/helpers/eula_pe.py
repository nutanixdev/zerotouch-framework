"""
Accept EULA on PE

Accepts the End-User License Agreement on Prism Element via the v1 eulas
API. Distinct from the PC-scoped ``eula`` entity (licensing v4 API): this
targets a standalone PE cluster directly and has no v4 equivalent since the
v4 licensing EULA endpoints have no cluster-targeting field.

API: POST /api/nutanix/v1/eulas/accept
"""

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.log_utils import get_logger
from ztf.helpers.utils.rest_utils import RestAPIUtil


class EulaPeHelper(PeEntityV1):
    """Helper for accepting the EULA directly on a Prism Element cluster."""

    def __init__(
        self,
        session: RestAPIUtil,
        proxy_cluster_uuid: str | None = None,
        logger=None,
        data: dict | None = None,
    ):
        self.resource_type = "/eulas"
        self.logger = logger if logger else get_logger(__name__)
        self.data = data or {}
        super().__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def _is_eula_accepted(self) -> bool:
        """Check if EULA is already accepted."""
        try:
            resp = self.read()
            if isinstance(resp, list):
                for entity in resp:
                    if isinstance(entity, dict) and "userDetailsList" in entity:
                        return True
            return False
        except Exception:
            return False

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Accept the EULA on PE.

        Expected entity_data:
            username: str - Username accepting EULA
            company_name: str - Company name
            job_title: str - Job title

        :return: "eula_accepted" as ext_id
        """
        required = ["username", "company_name", "job_title"]
        for field in required:
            if field not in entity_data:
                raise ValueError(f"Required field '{field}' missing")

        if self._is_eula_accepted():
            self.logger.info("EULA already accepted, skipping")
            return "eula_accepted"

        data = {
            "username": entity_data["username"],
            "companyName": entity_data["company_name"],
            "jobTitle": entity_data["job_title"],
        }

        try:
            self.create(data=data, endpoint="accept")
            self.logger.info("EULA accepted successfully")
            return "eula_accepted"
        except Exception as e:
            self.logger.error(f"Failed to accept EULA: {e}")
            raise

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        raise NotImplementedError("EULA cannot be updated")

    def delete_entity(self, ext_id: str) -> bool:
        raise NotImplementedError("EULA cannot be un-accepted")

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """List EULA acceptance status."""
        if self._is_eula_accepted():
            return [{"extId": "eula_accepted", "status": "accepted"}]
        return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """Check EULA acceptance status.

        Always returns ``None``, even when accepted: the v1 ``/eulas``
        read API has no reliable way to report back ``username`` /
        ``company_name`` / ``job_title`` in the same shape ``create_entity``
        accepts, and since ``update_entity``/``delete_entity`` are not
        supported there is nothing meaningful to diff against user config
        anyway. Returning ``None`` tells callers (e.g. ``ztf refresh``) to
        keep the last-known state rather than compare mismatched shapes.
        """
        return None
