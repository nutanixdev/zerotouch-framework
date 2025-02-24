import traceback
from typing import Dict
from framework.helpers.helper_functions import read_creds
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.ndb.clusters import Cluster
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class RegisterInitClusterNdb(Script):
    """
    The Script to add register initial cluster in ndb
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.ndb_ip = self.data["ndb_ip"]
        self.ndb_session = self.data["ndb_session"]
        self.cluster = self.data.get("register_clusters", [None])[0]
        self.cluster_op = Cluster(self.ndb_session)
        super(RegisterInitClusterNdb, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if not self.cluster:
                raise Exception("Cluster details not found in the payload")

            cluster_credential = self.cluster.get('pe_credential')
            # get credentials from the payload
            try:
                pe_username, pe_password = read_creds(data=self.data, credential=cluster_credential)
            except Exception as e:
                self.exceptions.append(e)
                return

            self.cluster["username"] = pe_username
            self.cluster["password"] = pe_password

            cluster_spec, error = self.cluster_op.get_new_cluster_spec(self.cluster)
            if error:
                raise Exception(error)

            response = self.cluster_op.create(data=cluster_spec)

            if "id" in response:
                self.logger.info(f"Initial Cluster registered successfully in NDB")

                self.logger.info("Uploading the cluster spec to the NDB")
                _ = self.cluster_op.set_cluster_json(cluster_info=response)
            else:
                self.exceptions.append(f"Could not register the initial cluster in NDB. Error: {response}")
        except Exception as e:
            tb_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
            self.exceptions.append(
                f"{type(self).__name__} failed for the NDB {self.data['ndb_ip']!r} with the error: {e} \n {tb_str}")

    def verify(self, **kwargs):
        try:
            self.results[self.ndb_ip] = {
                "register_clusters":
                    {
                        self.cluster["name"]: "CAN'T VERIFY"
                    }
            }

            response, error = self.cluster_op.get_cluster(name=self.cluster["name"])
            if error:
                raise Exception(error)

            if response and response.get("id"):
                self.results[self.ndb_ip]["register_clusters"][self.cluster["name"]] = "PASS"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for "
                             f"{self.ndb_ip}")
