"""
Add Active Directory Server on PE

Adds a directory service (Active Directory / LDAP) to Prism Element via the
v1 authconfig API. No v4 equivalent: v4 IAM directory services configure
authentication into Prism Central, not a standalone PE cluster's local
Prism auth config.

API: POST /api/nutanix/v1/authconfig/directories
"""

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.log_utils import get_logger
from ztf.helpers.utils.rest_utils import RestAPIUtil


class AdServerPeHelper(PeEntityV1):
    """Helper for registering an Active Directory/LDAP server on PE."""

    def __init__(
        self,
        session: RestAPIUtil,
        proxy_cluster_uuid: str | None = None,
        logger=None,
        data: dict | None = None,
    ):
        self.resource_type = "/authconfig"
        self.logger = logger if logger else get_logger(__name__)
        self.data = data or {}
        super().__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Add an Active Directory server to PE.

        Expected entity_data:
            ad_name: str - Directory name
            ad_domain: str - AD domain (e.g. "corp.nutanix.com")
            ad_directory_url: str - LDAP URL (e.g. "ldap://10.0.0.1:389")
            directory_type: str - "ACTIVE_DIRECTORY" or "OPEN_LDAP"
            service_account_username: str - Bind DN or username
            service_account_password: str - Bind password
            group_search_type: str - Optional, default "NON_RECURSIVE"
            connection_type: str - Optional, default "LDAP"

        :return: ad_name as ext_id
        """
        required = [
            "ad_name",
            "ad_domain",
            "ad_directory_url",
            "directory_type",
            "service_account_username",
            "service_account_password",
        ]
        for field in required:
            if field not in entity_data:
                raise ValueError(f"Required field '{field}' missing")

        ad_name = entity_data["ad_name"]

        existing = self.list_entities()
        for d in existing:
            if d.get("ad_name") == ad_name:
                self.logger.info(f"Directory '{ad_name}' already exists, skipping")
                return ad_name

        spec = {
            "name": ad_name,
            "domain": entity_data["ad_domain"],
            "directoryUrl": entity_data["ad_directory_url"],
            "groupSearchType": entity_data.get("group_search_type", "NON_RECURSIVE"),
            "directoryType": entity_data["directory_type"],
            "connectionType": entity_data.get("connection_type", "LDAP"),
            "serviceAccountUsername": entity_data["service_account_username"],
            "serviceAccountPassword": entity_data["service_account_password"],
        }

        try:
            self.create(data=spec, endpoint="directories")
            self.logger.info(f"Added directory service '{ad_name}'")
            return ad_name
        except Exception as e:
            self.logger.error(f"Failed to add directory '{ad_name}': {e}")
            raise

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        raise NotImplementedError("Update not supported for AD server")

    def delete_entity(self, ext_id: str) -> bool:
        """Delete a directory service by name."""
        try:
            self.delete(endpoint=f"directories/{ext_id}")
            self.logger.info(f"Deleted directory service '{ext_id}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete directory '{ext_id}': {e}")
            raise

    @staticmethod
    def _to_entity_data(raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw PE v1 directory-service response back to the
        snake_case keys ``create_entity`` accepts (see ``helper_schema``
        in ``entity_map.py``), so state bodies read back via
        ``get_entity_by_ext_id``/``list_entities`` stay comparable to
        user config for drift detection.

        ``service_account_password`` is intentionally omitted: it is a
        write-only field the v1 API never returns in a GET.
        """
        return {
            "extId": raw.get("name"),
            "ad_name": raw.get("name"),
            "ad_domain": raw.get("domain"),
            "ad_directory_url": raw.get("directoryUrl"),
            "directory_type": raw.get("directoryType"),
            "connection_type": raw.get("connectionType"),
            "group_search_type": raw.get("groupSearchType"),
            "service_account_username": raw.get("serviceAccountUsername"),
        }

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """List all directory services."""
        try:
            resp = self.read(endpoint="directories")
            if isinstance(resp, list):
                entities: list[dict[str, Any]] = [
                    self._to_entity_data(d) for d in resp if isinstance(d, dict)
                ]
            else:
                entities = []
            if custom_filter and custom_filter.get("ad_name"):
                entities = [
                    e for e in entities if e.get("ad_name") == custom_filter["ad_name"]
                ]
            return entities
        except Exception as e:
            self.logger.error(f"Failed to list directories: {e}")
            return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """Get directory service by name."""
        entities = self.list_entities()
        for e in entities:
            if e.get("extId") == ext_id:
                return {k: v for k, v in e.items() if k != "extId"}
        return None
