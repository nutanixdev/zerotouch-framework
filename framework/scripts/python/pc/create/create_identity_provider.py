import os
from copy import deepcopy
from typing import Dict
from urllib.request import urlopen
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.v3.identity_provider import IdentityProvider
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateIdp(Script):
    """
    Class that creates an Identity Provider in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.idp_configs = self.data.get("saml_idp_configs")
        super(CreateIdp, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if self.idp_configs:
                idp_payload_list = []
                idp_op = IdentityProvider(self.pc_session)

                for idp_config in deepcopy(self.idp_configs):
                    self.logger.info(f"Adding Identity Providers in {self.data['pc_ip']!r}")

                    if not (idp_name := idp_config.pop("name", "")):
                        self.exceptions.append("Need IDP Name")
                        return

                    idp_properties = idp_config.pop("idp_properties", {})
                    idp_metadata = None

                    if (not idp_config.get("metadata_url") and not idp_properties and
                       not idp_config.get("metadata_path")):
                        self.exceptions.append("Need either Metadata URL or Metadata Path or IDP Properties")
                        continue

                    if idp_config.get("metadata_url"):
                        metadata_url = idp_config.pop("metadata_url")
                        try:
                            idp_metadata = urlopen(metadata_url).read()
                            idp_metadata = idp_metadata.decode("utf-8")
                        except Exception as e:
                            self.exceptions.append(f"Failed to read metadata from "
                                                   f"{metadata_url!r} with the error: {e}")
                            continue
                    elif idp_config.get("metadata_path"):
                        metadata_path = idp_config.pop("metadata_path")
                        try:
                            metadata_path = os.path.join(self.data["project_root"], metadata_path)
                            if os.path.isfile(metadata_path):
                                with open(metadata_path, "r") as file:
                                    idp_metadata = file.read()
                            else:
                                self.exceptions.append(f"Metadata file {metadata_path!r} not found")
                                continue
                        except Exception as e:
                            self.exceptions.append(f"Failed to read metadata from {metadata_path!r} with the error: "
                                                   f"{e}")
                            continue
                    else:
                        idp_list = idp_op.list()
                        idp_url_list = [idp["spec"]["resources"]["idp_url"] for idp in idp_list
                                        if idp.get("spec", {}).get("resources", {}).get("idp_url")]
                        if idp_properties.get("idp_url") in idp_url_list:
                            self.exceptions.append(f"IDP with URL {idp_properties.get('idp_url')!r} already exists")
                            continue

                    payload = idp_op.get_payload(name=idp_name, idp_metadata=idp_metadata,
                                                 idp_properties=idp_properties, **idp_config)
                    idp_payload_list.append(payload)

                if not idp_payload_list:
                    self.logger.warning(f"No IDPs to create, skipping adding Identity Providers in "
                                        f"{self.data['pc_ip']!r}")
                    return

                logger.info(f"Trigger batch create API for Identity Providers in {self.data['pc_ip']!r}")
                task_uuid_list = idp_op.batch_op.batch_create(request_payload_list=idp_payload_list)

                # Monitor the tasks
                if task_uuid_list:
                    app_response, status = TaskMonitor(self.pc_session,
                                                       task_uuid_list=task_uuid_list).monitor()

                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append(
                            "Timed out. Creation of Identity Providers in PC didn't happen in the prescribed timeframe")
            else:
                self.logger.info(f"No IDP config found, skipping adding Identity Providers in {self.data['pc_ip']!r}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.idp_configs:
            return

        # Initial status
        self.results["CreateIdentityProviders"] = {}

        idp_op = IdentityProvider(self.pc_session)
        idp_list = []
        idp_name_list = []

        for idp_config in self.idp_configs:
            # Initial status
            self.results["CreateIdentityProviders"][idp_config['name']] = "CAN'T VERIFY"

            idp_list = idp_list or idp_op.list()
            idp_name_list = idp_name_list or [idp.get("spec", {}).get("name")
                                              for idp in idp_list if
                                              idp.get("spec", {}).get("name")]
            if idp_config['name'] in idp_name_list:
                self.results["CreateIdentityProviders"][idp_config['name']] = "PASS"
            else:
                self.results["CreateIdentityProviders"][idp_config['name']] = "FAIL"
