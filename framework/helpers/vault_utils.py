"""
Function to authenticate with the cyber ark instance using certificate and key
"""
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil

logger = get_logger(__name__)


class CyberArk:
    def __init__(self, host: str, cert_file: str, cert_key: str, port: str = "", ):
        self.cert_file = cert_file
        self.cert_key = cert_key
        self.logger = logger
        self.session = RestAPIUtil(ip_address=host, user=None, pwd=None, port=port)

    def fetch_creds(self, username: str, app_id: str, safe: str, address: str, endpoint: str):
        """
        Fetch password from the vault.
        params:
        username: account name
        app_id: application id
        safe: safe name where the account is saved
        address: address of the entity
        return: username, password of the account
        """
        uri = f"{endpoint}/api/Accounts?AppID={app_id}&Query=Safe={safe};UserName={username};Address={address}"
        try:
            user_pwd_details = self.session.get(uri, verify=self.cert_file, cert=(self.cert_file, self.cert_key))
            return user_pwd_details.get("UserName"), user_pwd_details.get("Content")
        except Exception as e:
            raise Exception(f"Failed to fetch password for user: {username!r}. Error is: {e}").with_traceback(e.__traceback__)
