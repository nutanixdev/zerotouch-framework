"""
Update CVM Foundation Helper

This helper provides backward compatibility for updating CVM foundation via SSH.
It implements the entity_handler interface similar to name_servers and ntp_servers helpers.
"""

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.rest_utils import RestAPIUtil
from ztf.helpers.utils.ssh_cvm import SSHCvm
from ztf.utils.utils import get_logger


class UpdateCvmFoundationHelper(PeEntityV1):
    """
    Helper for updating CVM foundation via SSH.

    This helper implements the entity_handler interface methods (create_entity, etc.)
    similar to NameServersHelper and NtpServersHelper.
    """

    def __init__(
        self,
        session: RestAPIUtil,
        proxy_cluster_uuid: str | None = None,
        logger=None,
        data: dict | None = None,
    ):
        """
        Initialize UpdateCvmFoundationHelper.

        Args:
            session: RestAPIUtil session (not used for SSH operations, but required by base class)
            proxy_cluster_uuid: Optional cluster UUID for proxy operations
            logger: Optional logger instance
            data: Configuration data dictionary (needed for credential access)
        """
        self.resource_type = "/cluster"
        self.logger = logger if logger else get_logger(__name__)
        self.data = data or {}
        super().__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    # Entity handler interface methods
    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Create/update CVM foundation on a single CVM.

        Expected entity_data format:
        {
            "cvm_ip": "10.0.0.1",
            "cvm_credential": "cvm_creds",
            "foundation_build_url": "http://...",
            "foundation_version": "x.x.x",
            "nameserver": "8.8.8.8",  # Optional
            "downgrade": false  # Optional
        }

        :param entity_data: Dictionary with CVM update configuration
        :return: CVM IP as ext_id
        :raises ValueError: If required fields are missing
        :raises Exception: If update fails
        """
        # Validate required fields
        required_fields = [
            "cvm_ip",
            "cvm_credential",
            "foundation_build_url",
            "foundation_version",
        ]
        for field in required_fields:
            if field not in entity_data:
                raise ValueError(f"Required field '{field}' is missing in entity_data")

        cvm_ip = entity_data["cvm_ip"]
        cvm_details = {
            "cvm_credential": entity_data["cvm_credential"],
            "foundation_build_url": entity_data["foundation_build_url"],
            "foundation_version": entity_data["foundation_version"],
            "nameserver": entity_data.get("nameserver"),
            "downgrade": entity_data.get("downgrade", False),
        }

        try:
            cvm_credential = cvm_details.get("cvm_credential")
            if not cvm_credential:
                raise ValueError(f"{cvm_ip}: CVM Credentials are not provided")

            creds = self.data.get("credentials", {})
            if isinstance(cvm_credential, dict):
                cvm_username = cvm_credential.get("username")
                cvm_password = cvm_credential.get("password")
            elif isinstance(creds.get(cvm_credential), dict):
                cvm_username = creds[cvm_credential].get("username")
                cvm_password = creds[cvm_credential].get("password")
            else:
                raise ValueError(
                    f"{cvm_ip}: Cannot resolve credential '{cvm_credential}'"
                )

            if not cvm_username or not cvm_password:
                raise ValueError(f"{cvm_ip}: CVM username or password is empty")

            ssh_cvm = None
            try:
                ssh_cvm = SSHCvm(cvm_ip, cvm_username, cvm_password)

                if cvm_details.get("nameserver"):
                    status, error = ssh_cvm.update_resolv_conf(
                        cvm_details["nameserver"]
                    )
                    if not status:
                        self.logger.warning(
                            f"{cvm_ip}: Failed to update nameserver in resolv.conf {error}"
                        )

                status, error_message = ssh_cvm.update_cvm_foundation(
                    foundation_url_path=cvm_details["foundation_build_url"],
                    downgrade=cvm_details.get("downgrade", False),
                )
            finally:
                if ssh_cvm is not None:
                    ssh_cvm.close()

            if not status:
                raise Exception(
                    f"{cvm_ip}: Failed to update CVM foundation: {error_message}"
                )

            self.logger.info(f"{cvm_ip}: Successfully updated CVM foundation")
            return cvm_ip

        except Exception as e:
            self.logger.error(
                f"Failed to create/update CVM foundation on {cvm_ip}: {e}"
            )
            raise

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        """
        Update CVM foundation (same as create for this entity).

        :param ext_id: CVM IP address
        :param entity_data: Dictionary with CVM update configuration
        :return: CVM IP as ext_id
        """
        # For CVM foundation update, update is the same as create
        # Ensure cvm_ip matches ext_id
        if "cvm_ip" not in entity_data:
            entity_data["cvm_ip"] = ext_id
        elif entity_data["cvm_ip"] != ext_id:
            self.logger.warning(
                f"cvm_ip in entity_data ({entity_data['cvm_ip']}) doesn't match ext_id ({ext_id}). Using ext_id."
            )
            entity_data["cvm_ip"] = ext_id

        return self.create_entity(entity_data)

    def delete_entity(self, ext_id: str) -> bool:
        """
        Delete operation is not supported for CVM foundation.

        :param ext_id: CVM IP address
        :raises NotImplementedError: Delete is not supported
        """
        raise NotImplementedError(
            "Delete operation is not supported for CVM foundation updates"
        )

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """
        List operation is not directly supported for CVM foundation.
        This would require SSH access to all CVMs to check versions.

        :param custom_filter: Filter dict (not used)
        :param kwargs: Additional parameters
        :return: Empty list (listing requires SSH access to all CVMs)
        """
        self.logger.warning(
            "List operation for CVM foundation requires SSH access to all CVMs. Not implemented."
        )
        return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """
        Get CVM foundation information by CVM IP.
        This requires SSH access to verify the foundation version.

        :param ext_id: CVM IP address
        :return: Entity dict if verification successful, None otherwise
        """
        # This would require credentials in data, which might not be available
        # For now, return None as we can't verify without credentials
        self.logger.warning(
            f"get_entity_by_ext_id for CVM foundation requires credentials. Cannot verify {ext_id} without credentials."
        )
        return None
