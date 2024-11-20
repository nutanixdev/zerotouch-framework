from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v1.authentication import AuthN
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteRoleMappingPc(Script):
    """
    The Script to delete role mapping in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.authn_payload = self.data.get("pc_directory_services") or self.data.get("directory_services", {})
        super(DeleteRoleMappingPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            authn = AuthN(self.pc_session)
            if not self.authn_payload.get("ad_name") or not self.authn_payload.get("role_mappings"):
                self.logger.warning(f"Authentication payload not specified for the PC {self.data['pc_ip']!r}")
                return

            existing_role_mapping = authn.get_role_mappings(directory_name=self.authn_payload["ad_name"])
            existing_roles = set([(mapping["role"], mapping["entityType"]) for mapping in existing_role_mapping])

            for role_mapping in self.authn_payload["role_mappings"]:
                if (role_mapping.get("role_type"), role_mapping.get("entity_type")) not in existing_roles:
                    self.logger.warning(f"Role-mapping {role_mapping['role_type']}:{role_mapping['entity_type']}"
                                        f" doesn't exist in the directory {self.authn_payload['ad_name']} for the PC "
                                        f"{self.data['pc_ip']!r}")
                    continue

                self.logger.info(
                    f"Deleting role-mapping {role_mapping['role_type']}-{role_mapping['entity_type']} for the PC "
                    f"{self.data['pc_ip']!r}"
                )
                response = authn.delete_role_mapping(
                    directory_name=self.authn_payload["ad_name"],
                    role_mapping=role_mapping
                )

                if isinstance(response, str):
                    self.exceptions.append(response)

        except Exception as e:
            self.exceptions.append(e)
            return

    def verify(self, **kwargs):
        if not self.authn_payload.get("ad_name") or not self.authn_payload.get("role_mappings"):
            return

        # Check if Role mapping was deleted/ already not present
        self.results["Delete_Role_mappings"] = {}

        authn = AuthN(self.pc_session)

        existing_role_mappings = []
        existing_roles = set()

        for role_mapping in self.authn_payload.get("role_mappings"):
            # Initial status
            self.results["Delete_Role_mappings"][(self.authn_payload["ad_name"], role_mapping["role_type"], role_mapping["entity_type"])] = \
                "CAN'T VERIFY"
            existing_role_mappings = existing_role_mappings or authn.get_role_mappings(
                directory_name=self.authn_payload["ad_name"])
            existing_roles = existing_roles or set([mapping["role"] for mapping in existing_role_mappings])

            if (role_mapping.get("role_type"), role_mapping.get("entity_type")) not in existing_roles:
                self.results["Delete_Role_mappings"][(self.authn_payload["ad_name"], role_mapping["role_type"],
                                                      role_mapping["entity_type"])] = "PASS"
            else:
                self.results["Delete_Role_mappings"][(self.authn_payload["ad_name"], role_mapping["role_type"],
                                                      role_mapping["entity_type"])] = "FAIL"
