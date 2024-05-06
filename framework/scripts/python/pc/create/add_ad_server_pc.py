from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v1.authentication import AuthN
from framework.scripts.python.script import Script
from framework.helpers.helper_functions import read_creds

logger = get_logger(__name__)


class AddAdServerPc(Script):
    """
    The Script to add Active Directory in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.authn_payload = self.data.get("pc_directory_services") or self.data.get("directory_services", {})
        super(AddAdServerPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            authn = AuthN(self.pc_session)

            if not self.authn_payload and not self.authn_payload.get("ad_name"):
                self.logger.warning(f"Authentication payload not specified for the PC {self.data['pc_ip']!r}")
                return

            existing_directory_services = authn.get_directories()
            ad = next((ad for ad in existing_directory_services
                       if ad.get("name") == self.authn_payload["ad_name"]), None)

            if ad:
                self.logger.warning(f"{self.authn_payload['ad_name']!r} Directory already exists in"
                                    f" the PC {self.data['pc_ip']!r}")
                return

            self.logger.info(f"Creating a new Active Directory: {self.authn_payload['ad_name']!r}")

            if "service_account_credential" not in self.authn_payload:
                self.exceptions.append("Service account credential not specified for the Directory")
                return

            service_account_credential = self.authn_payload.pop("service_account_credential")
            # get credentials from the payload
            try:
                self.authn_payload["service_account_username"], self.authn_payload["service_account_password"] = (
                    read_creds(data=self.data, credential=service_account_credential))
            except Exception as e:
                self.exceptions.append(e)
                return

            response = authn.create_directory_services(**self.authn_payload)

            if isinstance(response, str):
                self.exceptions.append(response)
                return

            self.logger.info(f"{self.authn_payload['ad_name']!r} Directory created in the PC {self.data['pc_ip']!r}")
        except Exception as e:
            self.exceptions.append(
                f"{type(self).__name__} failed for the PC {self.data['pc_ip']!r} with the error: {e}")

    def verify(self, **kwargs):
        # Check if directory services were created

        try:
            if not self.authn_payload:
                return

            self.results["Create_Directory_services"] = "CAN'T VERIFY"

            authn = AuthN(self.pc_session)

            existing_directory_services = authn.get_directories()
            directory_services_name_list = [ad["name"] for ad in existing_directory_services]

            if self.authn_payload["ad_name"] in directory_services_name_list:
                self.results["Create_Directory_services"] = "PASS"
            else:
                self.results["Create_Directory_services"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} "
                             f"for the PC {self.data['pc_ip']!r}")
