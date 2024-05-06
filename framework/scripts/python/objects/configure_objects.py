from copy import deepcopy
from typing import Optional, Dict
from framework.scripts.python.pc.enable.enable_objects import EnableObjects
from framework.scripts.python.objects.objectstore.create_objectstore import CreateObjectStore
from framework.scripts.python.objects.directory.add_directory_service_oss import AddDirectoryServiceOss
from framework.scripts.python.objects.directory.add_ad_users_oss import AddAdUsersOss
from framework.scripts.python.objects.buckets.create_bucket import CreateBucket
from framework.scripts.python.objects.buckets.share_bucket import ShareBucket
from framework.scripts.python.helpers.batch_script import BatchScript
from framework.scripts.python.script import Script
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class OssConfig(Script):
    """
    Configure Objects with below configs
    """

    def __init__(self, data: Dict, global_data: Dict, results_key: str = "", log_file: Optional[str] = None, **kwargs):
        self.data = deepcopy(data)
        self.global_data = deepcopy(global_data)
        self.results_key = results_key
        self.log_file = log_file
        super(OssConfig, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        if not self.data.get("vaults"):
            self.data["vaults"] = self.global_data.get("vaults")
        if not self.data.get("vault_to_use"):
            self.data["vault_to_use"] = self.global_data.get("vault_to_use")

        objects_batch_scripts = BatchScript(results_key=self.results_key)

        objects_batch_scripts.add_all([
            EnableObjects(self.data, log_file=self.log_file),
            CreateObjectStore(self.data, log_file=self.log_file),
            AddDirectoryServiceOss(self.data, log_file=self.log_file),
            AddAdUsersOss(self.data, log_file=self.log_file),
            CreateBucket(self.data, log_file=self.log_file),
            ShareBucket(self.data, log_file=self.log_file)
        ])

        self.results.update(objects_batch_scripts.run())

    def verify(self):
        pass
