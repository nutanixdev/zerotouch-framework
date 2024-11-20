from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v1.authentication import AuthN
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateRoleMappingPc(Script):
    """
    The Script to create role mapping in PC
    """
    LOAD_TASK = False
    DEFAULT_ROLE_MAPPINGS = [
        {
            "role_type": "ROLE_CLUSTER_ADMIN",
            "entity_type": "OU",
            "values": ["admin"]
        },
        {
            "role_type": "ROLE_USER_ADMIN",
            "entity_type": "OU",
            "values": ["user"]
        },
        {
            "role_type": "ROLE_CLUSTER_VIEWER",
            "entity_type": "OU",
            "values": ["viewer"]
        }
    ]

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.authn_payload = self.data.get("pc_directory_services") or self.data.get("directory_services", {})
        super(CreateRoleMappingPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            authn = AuthN(self.pc_session)
            if not self.authn_payload.get("ad_name") or not self.authn_payload.get("role_mappings"):
                self.logger.warning(f"Authentication payload not specified for the PC {self.data['pc_ip']!r}")
                return

            existing_role_mapping = authn.get_role_mappings(directory_name=self.authn_payload["ad_name"])
            existing_roles = set([mapping["role"] for mapping in existing_role_mapping])

            for role_mapping in self.authn_payload["role_mappings"]:
                if role_mapping.get("role_type") in existing_roles:
                    self.logger.warning(f"Role {role_mapping['role_type']} already exists. Skipping...")
                    continue

                self.logger.info(f"Creating new role-mapping for the PC {self.data['pc_ip']!r}")
                response = authn.create_role_mapping(
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

        # Check if Role mapping was created/ was already present
        self.results["Create_Role_mappings"] = {}

        authn = AuthN(self.pc_session)

        existing_role_mappings = []
        existing_roles = set()

        for role_mapping in self.authn_payload.get("role_mappings"):
            # Initial status
            self.results["Create_Role_mappings"][role_mapping["role_type"]] = \
                "CAN'T VERIFY"

            existing_role_mappings = existing_role_mappings or authn.get_role_mappings(
                directory_name=self.authn_payload["ad_name"])
            existing_roles = existing_roles or set([mapping["role"] for mapping in existing_role_mappings])

            if role_mapping.get("role_type") in existing_roles:
                self.results["Create_Role_mappings"][role_mapping["role_type"]] = "PASS"
            else:
                self.results["Create_Role_mappings"][role_mapping["role_type"]] = "FAIL"
