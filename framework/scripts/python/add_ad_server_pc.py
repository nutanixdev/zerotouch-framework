from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .helpers.v1.authentication import AuthN
from .script import Script

logger = get_logger(__name__)


class AddAdServerPc(Script):
    """
    The Script to add Active Directory in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = RestAPIUtil(self.data['pc_ip'], user="admin",
                                      pwd=self.data['admin_pc_password'],
                                      port="9440", secured=True) \
            if self.data.get('admin_pc_password') else self.data["pc_session"]
        self.authn_payload = self.data.get("pc_directory_services") or self.data.get("directory_services", {})
        super(AddAdServerPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            authn = AuthN(self.pc_session)

            if not self.authn_payload and not self.authn_payload.get("ad_name"):
                self.logger.warning(f"Authentication payload not specified for the PC '{self.data['pc_ip']}'")
                return

            existing_directory_services = authn.get_directories()
            ad = next((ad for ad in existing_directory_services
                       if ad.get("name") == self.authn_payload["ad_name"]), None)

            if ad:
                self.logger.warning(f"'{self.authn_payload['ad_name']}' Directory already exists in"
                                    f" the PC '{self.data['pc_ip']}'")
                return

            self.logger.info(f"Creating new Directory '{self.authn_payload['ad_name']}'")
            response = authn.create_directory_services(**self.authn_payload)

            if isinstance(response, str):
                self.exceptions.append(response)

            self.logger.info(f"'{self.authn_payload['ad_name']}' Directory created in the PC '{self.data['pc_ip']}'")
        except Exception as e:
            self.exceptions.append(
                f"{type(self).__name__} failed for the PC '{self.data['pc_ip']}' with the error: {e}")

    def verify(self, **kwargs):
        # Check if directory services were created

        try:
            self.results["Create_Directory_services"] = "CAN'T VERIFY"

            authn = AuthN(self.pc_session)

            if not self.authn_payload:
                return

            existing_directory_services = authn.get_directories()
            directory_services_name_list = [ad["name"] for ad in existing_directory_services]

            if self.authn_payload["ad_name"] in directory_services_name_list:
                self.results["Create_Directory_services"] = "PASS"
            else:
                self.results["Create_Directory_services"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}' "
                             f"for the PC '{self.data['pc_ip']}'")
