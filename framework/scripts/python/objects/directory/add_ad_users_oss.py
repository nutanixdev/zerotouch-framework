from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.objects.iam_proxy import IamProxyObjects
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class AddAdUsersOss(Script):
    """
    Class that adds AdUsers in Objects
    """
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.ad_configs = self.data.get("oss_directory_services", []) or self.data.get("objects", {}). \
            get("directory_services", [])
        super(AddAdUsersOss, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            iam_proxy_obj = IamProxyObjects(self.pc_session)

            if self.ad_configs:
                for ad_config in self.ad_configs:
                    if not ad_config.get("ad_users", []):
                        continue
                    idp = iam_proxy_obj.get_by_domain_name(ad_config.get("ad_domain"))
                    if idp:
                        idp_uuid = idp["metadata"]["uuid"]
                        response = iam_proxy_obj.create_ad_users(
                            idp_uuid,
                            ad_config["ad_users"]
                        )
                        logger.debug(response)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.ad_configs:
            return

        for ad_config in self.ad_configs:
            # Initial status
            self.results["AddAdUsersOss"] = {}

            iam_proxy_obj = IamProxyObjects(self.pc_session)

            try:
                users = iam_proxy_obj.list_users()
                exiting_usernames = set([user.get("username") for user in users])

                for ad_user in ad_config.get("ad_users", []):
                    if ad_user in exiting_usernames:
                        self.results["AddAdUsersOss"][ad_user] = "PASS"
                    else:
                        self.results["AddAdUsersOss"][ad_user] = "FAIL"
            except Exception as e:
                self.logger.debug(e)
                self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r}")
