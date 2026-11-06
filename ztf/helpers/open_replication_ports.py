"""
Open Replication Ports Helper

Backward-compatible helper for opening replication ports (2020, 2030, 2036,
2073, 2090) on cluster CVMs via SSH. SSH-only; no firewall/port-open API in
any v4 namespace. Implements the entity_handler interface like
update_cvm_foundation.
"""

from __future__ import annotations

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.rest_utils import RestAPIUtil
from ztf.helpers.utils.ssh_cvm import SSHCvm
from ztf.utils.utils import get_logger

DEFAULT_REPLICATION_PORTS = [2020, 2030, 2036, 2073, 2090]


class OpenReplicationPortsHelper(PeEntityV1):
    """
    Helper for opening replication ports on cluster CVMs via SSH.

    SSHes to a CVM in the cluster and uses allssh + modify_firewall to
    open ports on all CVMs in the cluster.
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

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Open replication ports on all CVMs in a cluster via SSH.

        Expected entity_data:
        {
            "cluster_ip": "10.x.x.x",          # Cluster VIP or CVM IP
            "cvm_credential": "cvm_creds",       # Credential key
            "ports": [2020, 2030, 2036, 2073, 2090]  # Optional, defaults to standard ports
        }

        :return: cluster_ip as ext_id
        """
        cluster_ip = entity_data.get("cluster_ip")
        cvm_credential = entity_data.get("cvm_credential")
        ports = entity_data.get("ports", DEFAULT_REPLICATION_PORTS)

        if not cluster_ip:
            raise ValueError("entity_data must contain 'cluster_ip'")
        if not cvm_credential:
            raise ValueError("entity_data must contain 'cvm_credential'")

        if isinstance(cvm_credential, dict):
            cvm_username = cvm_credential.get("username") or cvm_credential.get("user")
            cvm_password = cvm_credential.get("password") or cvm_credential.get("pwd")
        else:
            creds = self.data.get("credentials", {})
            cred_data = creds.get(cvm_credential)
            if not isinstance(cred_data, dict):
                raise ValueError(
                    f"{cluster_ip}: Cannot resolve credential '{cvm_credential}'"
                )
            cvm_username = cred_data.get("username")
            cvm_password = cred_data.get("password")

        if not cvm_username or not cvm_password:
            raise ValueError(f"{cluster_ip}: CVM username or password is empty")

        ssh_cvm = None
        try:
            ssh_cvm = SSHCvm(
                cvm_ip=cluster_ip, username=cvm_username, password=cvm_password
            )
            success, output = ssh_cvm.enable_replication_ports(ports=ports)

            if not success:
                raise RuntimeError(
                    f"{cluster_ip}: Failed to open replication ports: {output}"
                )

            ports_str = ", ".join(str(p) for p in ports)
            self.logger.info(
                f"{cluster_ip}: Opened replication ports [{ports_str}] on all CVMs"
            )
            return cluster_ip

        except Exception as e:
            self.logger.error(f"Failed to open replication ports on {cluster_ip}: {e}")
            raise
        finally:
            if ssh_cvm is not None:
                ssh_cvm.close()

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        """Update is the same as create (idempotent port-open operation)."""
        if "cluster_ip" not in entity_data:
            entity_data["cluster_ip"] = ext_id
        return self.create_entity(entity_data)

    def delete_entity(self, ext_id: str) -> bool:
        """
        Closing replication ports is not supported via this helper.
        Manual intervention required.
        """
        raise NotImplementedError(
            "Closing replication ports is not supported via this helper"
        )

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """
        Cannot list open ports without SSH access to each cluster.
        Returns empty list.
        """
        self.logger.warning(
            "list_entities for replication ports requires SSH access; not implemented"
        )
        return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """
        Cannot verify port status without SSH access.
        """
        self.logger.warning(
            f"get_entity_by_ext_id for replication ports requires SSH access to {ext_id}"
        )
        return None
