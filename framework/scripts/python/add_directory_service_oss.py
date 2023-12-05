from typing import Dict
from framework.helpers.log_utils import get_logger
from .helpers.objects.iam_proxy import IamProxyObjects
from .script import Script

logger = get_logger(__name__)


class AddDirectoryServiceOss(Script):
    """
    Class that adds DirectoryService in Objects
    """
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.ad_configs = self.data.get("oss_directory_services", []) or self.data.get("objects", {}). \
            get("directory_services", [])
        super(AddDirectoryServiceOss, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            iam_proxy_obj = IamProxyObjects(self.pc_session)

            if self.ad_configs:
                for ad_config in self.ad_configs:
                    if iam_proxy_obj.get_by_domain_name(ad_config.get("ad_domain")):
                        self.logger.warning(f"SKIP: Directory with domain {ad_config['ad_domain']} is "
                                            f"already present in '{self.data['pc_ip']}'")
                        continue
                    response = iam_proxy_obj.add_directory_service(
                        ad_name=ad_config["ad_name"],
                        ad_domain=ad_config["ad_domain"],
                        ad_server_ip=ad_config["ad_server_ip"],
                        service_account_username=ad_config["service_account_username"],
                        service_account_password=ad_config["service_account_password"]
                    )
                    logger.debug(response)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.ad_configs:
            return

        for ad_config in self.ad_configs:
            # Initial status
            self.results["AddDirectoryServiceOss"] = {
                ad_config["ad_name"]: "CAN'T VERIFY"
            }

            iam_proxy_obj = IamProxyObjects(self.pc_session)

            try:
                if iam_proxy_obj.get_by_domain_name(ad_config.get("ad_domain")):
                    self.results["AddDirectoryServiceOss"][ad_config["ad_name"]] = "PASS"
                else:
                    self.results["AddDirectoryServiceOss"][ad_config["ad_name"]] = "FAIL"
            except Exception as e:
                self.logger.debug(e)
                self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}'")
