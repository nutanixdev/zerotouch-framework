from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.objects.buckets import Buckets
from framework.scripts.python.helpers.objects.objectstore import ObjectStore
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class ShareBucket(Script):
    """
    Class that shares a bucket with a list of users
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.object_stores = self.data.get("objectstores") or self.data.get("objects", {}). \
            get("objectstores", [])
        super(ShareBucket, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            os = ObjectStore(self.pc_session)
            bucket = Buckets(self.pc_session)

            for object_store in self.object_stores:
                os_obj = os.get_entity_by_name(object_store["name"])
                if not os_obj:
                    self.logger.warning(f"SKIP: Objectstore with name {object_store['name']} doesn't exist!")
                    continue
                os_uuid = os_obj["uuid"]
                if object_store.get("buckets"):
                    buckets = object_store["buckets"]
                    bucket_list = [bucket_config.get('name') for bucket_config in bucket.list_buckets(os_uuid)]

                    for bucket_config in buckets:
                        if bucket_config["name"] not in bucket_list:
                            self.logger.warning(f"SKIP: Bucket with name {bucket_config['name']} doesn't "
                                                f"exist in {self.data['pc_ip']!r}")
                            continue
                        try:
                            response = bucket.share_bucket(bucket_name=bucket_config['name'],
                                                           os_uuid=os_uuid,
                                                           usernames=bucket_config.get("user_access_list"))
                            logger.debug(response)
                        except Exception as e:
                            self.exceptions.append(f"Failed to share Bucket with name {bucket_config['name']}: "
                                                   f"{e}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # todo
        # Verification is tricky, will work later
        return
