import traceback
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.ndb.auth import Auth
from framework.scripts.python.helpers.ndb.clusters import Cluster
from framework.scripts.python.script import Script
from framework.helpers.helper_functions import read_creds

logger = get_logger(__name__)


class UpdatePasswordNdb(Script):
    """
    The Script to add update password in ndb
    """
    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.ndb_ip = self.data["ndb_ip"]
        self.default_ndb_password = self.data.get('default_ndb_password') or self.DEFAULT_SYSTEM_PASSWORD
        self.default_ndb_session = RestAPIUtil(self.ndb_ip,
                                               user=self.DEFAULT_USERNAME,
                                               pwd=self.default_ndb_password,
                                               secured=True)
        super(UpdatePasswordNdb, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            authn = Auth(self.default_ndb_session)

            new_ndb_admin_credential = self.data.get('new_ndb_admin_credential')
            if not new_ndb_admin_credential:
                raise Exception(f"No credential {new_ndb_admin_credential!r} found!")

            # get credentials from the payload
            try:
                _, new_ndb_password = read_creds(data=self.data, credential=new_ndb_admin_credential)
            except Exception as e:
                self.exceptions.append(e)
                return

            if new_ndb_password == self.default_ndb_password:
                self.logger.error(f"New Password specified is same as default password for NDB...")
                return

            response = authn.update_password(new_password=new_ndb_password)
            if response.get("status"):
                self.logger.info(f"Default System password updated with new password in NDB")
            else:
                self.exceptions.append(f"Could not change the NDB password. Error: {response}")
        except Exception as e:
            tb_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
            self.exceptions.append(
                f"{type(self).__name__} failed for the NDB {self.data['ndb_ip']!r} with the error: {e} \n {tb_str}")

    def verify(self, **kwargs):
        try:
            self.results[self.ndb_ip] = {
                "Change_Default_password_Ndb": "CAN'T VERIFY"
            }

            # Check if password is changed
            try:
                default_ndb_session = RestAPIUtil(self.ndb_ip,
                                                  user=self.DEFAULT_USERNAME,
                                                  pwd=self.default_ndb_password,
                                                  secured=True)
                cluster_obj = Cluster(default_ndb_session)
                cluster_obj.read()
                self.results[self.ndb_ip]["Change_Default_password_Ndb"] = "FAIL"
            except Exception:
                # if it fails, i.e default password doesn't work, password is changed
                self.results[self.ndb_ip]["Change_Default_password_Ndb"] = "PASS"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for "
                             f"{self.ndb_ip}")
