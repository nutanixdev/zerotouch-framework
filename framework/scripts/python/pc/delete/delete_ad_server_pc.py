from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v1.authentication import AuthN
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteAdServerPc(Script):
    """
    The Script to delete Active Directory in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.authn_payload = self.data.get("pc_directory_services") or self.data.get("directory_services", {})
        super(DeleteAdServerPc, self).__init__(**kwargs)
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

            if not ad:
                self.logger.warning(f"{self.authn_payload['ad_name']!r} Directory doesn't exist in"
                                    f" the PC {self.data['pc_ip']!r}")
                return

            self.logger.info(f"Deleting Directory {self.authn_payload['ad_name']!r}")
            response = authn.delete_directory_services(self.authn_payload['ad_name'])

            if isinstance(response, str):
                self.exceptions.append(response)
                return

            self.logger.info(f"{self.authn_payload['ad_name']!r} Directory deleted in the PC {self.data['pc_ip']!r}")
        except Exception as e:
            self.exceptions.append(
                f"{type(self).__name__!r} failed for the PC {self.data['pc_ip']!r} with the error: {e}")

    def verify(self, **kwargs):
        # Check if directory services were deleted

        try:
            if not self.authn_payload:
                return

            self.results["Delete_Directory_services"] = "CAN'T VERIFY"

            authn = AuthN(self.pc_session)

            existing_directory_services = authn.get_directories()
            directory_services_name_list = [ad["name"] for ad in existing_directory_services]

            if self.authn_payload["ad_name"] not in directory_services_name_list:
                self.results["Delete_Directory_services"] = "PASS"
            else:
                self.results["Delete_Directory_services"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} "
                             f"for the PC {self.data['pc_ip']!r}")
