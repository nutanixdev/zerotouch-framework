"""
Create Role Mapping on PE

Creates role mappings for an Active Directory on Prism Element via the v1
authconfig API. No v4 equivalent: v4 IAM role memberships and microseg
directory-to-category mappings operate on PC-managed identities/categories,
not a standalone PE cluster's local RBAC.

API: POST /api/nutanix/v1/authconfig/directories/{directory_name}/role_mappings
"""

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.log_utils import get_logger
from ztf.helpers.utils.rest_utils import RestAPIUtil


class RoleMappingPeHelper(PeEntityV1):
    """Helper for mapping AD groups/users/OUs to PE roles."""

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
        Create a role mapping for a directory service.

        Expected entity_data:
            directory_name: str - Name of the AD directory
            role_type: str - Role (e.g. "ROLE_CLUSTER_ADMIN", "ROLE_USER_ADMIN")
            entity_type: str - Entity type ("GROUP", "OU", "USER")
            values: list[str] - Entity values (group names, OUs, usernames)

        :return: "{directory_name}:{role_type}:{entity_type}" as ext_id
        """
        required = ["directory_name", "role_type", "entity_type", "values"]
        for field in required:
            if field not in entity_data:
                raise ValueError(f"Required field '{field}' missing")

        directory_name = entity_data["directory_name"]
        role_type = entity_data["role_type"]
        entity_type = entity_data["entity_type"]
        values = entity_data["values"]
        ext_id = f"{directory_name}:{role_type}:{entity_type}"

        existing = self.list_entities(custom_filter={"directory_name": directory_name})
        for mapping in existing:
            if (
                mapping.get("role_type") == role_type
                and mapping.get("entity_type") == entity_type
            ):
                self.logger.info(
                    f"Role mapping {role_type}/{entity_type} already exists "
                    f"for '{directory_name}', skipping"
                )
                return ext_id

        spec = {
            "directoryName": directory_name,
            "role": role_type,
            "entityType": entity_type,
            "entityValues": values,
        }

        endpoint = f"directories/{directory_name}/role_mappings"
        try:
            self.create(data=spec, endpoint=endpoint)
            self.logger.info(
                f"Created role mapping {role_type}/{entity_type} "
                f"for directory '{directory_name}'"
            )
            return ext_id
        except Exception as e:
            self.logger.error(f"Failed to create role mapping: {e}")
            raise

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        raise NotImplementedError("Update not supported — delete and recreate")

    def delete_entity(self, ext_id: str) -> bool:
        """
        Delete a role mapping.
        ext_id format: "directory_name:role_type:entity_type"
        """
        parts = ext_id.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"ext_id must be 'directory_name:role_type:entity_type', got '{ext_id}'"
            )
        directory_name, role_type, entity_type = parts

        endpoint = f"directories/{directory_name}/role_mappings"
        query = {"role": role_type, "entityType": entity_type}

        try:
            self.delete(endpoint=endpoint, query=query)
            self.logger.info(f"Deleted role mapping '{ext_id}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete role mapping '{ext_id}': {e}")
            raise

    @staticmethod
    def _to_entity_data(directory_name: str, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw PE v1 role-mapping response back to the snake_case
        keys ``create_entity`` accepts (see ``helper_schema`` in
        ``entity_map.py``), so state bodies read back via
        ``get_entity_by_ext_id``/``list_entities`` stay comparable to
        user config for drift detection.
        """
        role_type = raw.get("role")
        entity_type = raw.get("entityType")
        return {
            "extId": f"{directory_name}:{role_type}:{entity_type}",
            "directory_name": directory_name,
            "role_type": role_type,
            "entity_type": entity_type,
            "values": raw.get("entityValues"),
        }

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """
        List role mappings for a directory.
        custom_filter should contain 'directory_name'.
        """
        if not custom_filter or "directory_name" not in custom_filter:
            self.logger.warning("directory_name required in filter for list")
            return []

        directory_name = custom_filter["directory_name"]
        endpoint = f"directories/{directory_name}/role_mappings"

        try:
            resp = self.read(endpoint=endpoint)
            if isinstance(resp, list):
                return [
                    self._to_entity_data(directory_name, m)
                    for m in resp
                    if isinstance(m, dict)
                ]
            return []
        except Exception as e:
            self.logger.error(f"Failed to list role mappings: {e}")
            return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """Get role mapping by ext_id (directory_name:role_type:entity_type)."""
        parts = ext_id.split(":")
        if len(parts) != 3:
            return None
        directory_name, role_type, entity_type = parts

        mappings = self.list_entities(custom_filter={"directory_name": directory_name})
        for m in mappings:
            if m.get("role_type") == role_type and m.get("entity_type") == entity_type:
                return {k: v for k, v in m.items() if k != "extId"}
        return None
