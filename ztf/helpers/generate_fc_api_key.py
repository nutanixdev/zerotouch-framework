"""
Generate FC API Key Helper

Generates Foundation Central API keys via the FC API on Prism Central.
Implements the entity_handler interface.
"""

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.rest_utils import RestAPIUtil
from ztf.utils.utils import get_logger

FC_API_KEYS_PATH = "api/fc/v1/api_keys"
GENESIS_V1_PATH = "api/nutanix/v1/genesis"

_FC_ENABLED_PAYLOAD = {
    ".oid": "ClusterManager",
    ".method": "is_service_enabled",
    ".kwargs": {"service_name": "FoundationCentralService"},
}


class GenerateFcApiKeyHelper(PeEntityV1):
    """
    Helper for generating Foundation Central API keys.
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

    def _is_fc_enabled(self) -> bool:
        """Check if Foundation Central is enabled.

        Uses the Genesis v1 JSON-RPC endpoint to query
        ClusterManager.is_service_enabled, matching the zero-touch-ee
        approach.  Falls back to probing the FC API keys list endpoint
        if the Genesis call fails.
        """
        try:
            resp = self.session.post(GENESIS_V1_PATH, data=_FC_ENABLED_PAYLOAD)
            if isinstance(resp, dict) and resp.get(".return") is True:
                return True
        except Exception:
            self.logger.debug("Genesis v1 FC enabled check failed, trying fallback")

        # Fallback: probe the FC API keys endpoint
        try:
            resp = self.session.post(FC_API_KEYS_PATH + "/list", data={})
            if isinstance(resp, dict) and "api_keys" in resp:
                return True
        except Exception:
            self.logger.debug("FC API keys probe failed")

        return False

    def _list_api_keys(self) -> list[dict]:
        """List existing FC API keys. FC uses POST with empty body for listing."""
        try:
            resp = self.session.post(FC_API_KEYS_PATH + "/list", data={})
        except Exception:
            try:
                resp = self.session.post(FC_API_KEYS_PATH, data={})
            except Exception as e:
                self.logger.error(f"Failed to list FC API keys: {e}")
                raise
        if isinstance(resp, dict) and "api_keys" in resp:
            return resp["api_keys"]
        if isinstance(resp, dict) and "entities" in resp:
            return resp["entities"]
        if isinstance(resp, list):
            return resp
        return []

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Generate a new FC API key with the given alias.

        Expected entity_data:
            {"alias": "my-fc-key"} or {"fc_alias_key_name": "my-fc-key"}

        :return: alias as ext_id
        """
        alias = entity_data.get("alias") or entity_data.get("fc_alias_key_name")
        if not alias:
            raise ValueError("entity_data must contain 'alias' or 'fc_alias_key_name'")

        if not self._is_fc_enabled():
            raise RuntimeError("Foundation Central is not enabled on this PC")

        existing = self._list_api_keys()
        aliases = [
            k.get("alias") for k in existing if isinstance(k, dict) and k.get("alias")
        ]
        if alias in aliases:
            self.logger.info(
                f"FC API key with alias {alias!r} already exists. Skipping creation."
            )
            return alias

        try:
            resp = self.session.post(FC_API_KEYS_PATH, data={"alias": alias})
            if not resp or (isinstance(resp, dict) and not resp.get("api_key")):
                raise RuntimeError(f"Failed to generate FC API key: {resp}")
            self.logger.info(
                "FC API key generated successfully. Save it securely; it will not be shown again."
            )
            return alias
        except Exception as e:
            self.logger.error(f"Failed to generate FC API key: {e}")
            raise

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        raise NotImplementedError("Update operation is not supported for FC API keys")

    def delete_entity(self, ext_id: str) -> bool:
        raise NotImplementedError("Delete operation for FC API keys is not implemented")

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """List FC API key aliases (keys themselves are not returned by list)."""
        try:
            keys = self._list_api_keys()
            entities = [
                {"alias": k.get("alias"), "extId": k.get("alias")}
                for k in keys
                if isinstance(k, dict)
            ]
            if custom_filter:
                alias = custom_filter.get("alias")
                if alias is not None:
                    entities = [e for e in entities if e.get("alias") == alias]
            return entities
        except Exception as e:
            self.logger.error(f"Failed to list FC API keys: {e}")
            return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """Get FC API key info by alias (ext_id). Key value is not returned after creation."""
        try:
            keys = self._list_api_keys()
            for k in keys:
                if isinstance(k, dict) and k.get("alias") == ext_id:
                    return {"alias": ext_id, "extId": ext_id}
            return None
        except Exception as e:
            self.logger.error(f"Failed to get FC API key {ext_id}: {e}")
            return None
