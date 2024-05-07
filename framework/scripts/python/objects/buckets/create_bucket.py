from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.objects.buckets import Buckets
from framework.scripts.python.helpers.objects.objectstore import ObjectStore
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateBucket(Script):
    """
    Class that creates buckets
    """
    OWNER_UID = 19395
    OWNER_GID = 10000
    FILE_PERMISSION = "rw-rw-rw-"
    DIRECTORY_PERMISSION = "rwxrwxrwx"
    ANONYMOUS_UID = 65534
    ANONYMOUS_GID = 65534

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.object_stores = self.data.get("objectstores") or self.data.get("objects", {}). \
            get("objectstores", [])
        super(CreateBucket, self).__init__(**kwargs)
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
                    buckets_to_create = object_store["buckets"]
                    bucket_list = [bucket_config.get('name') for bucket_config in bucket.list_buckets(os_uuid)]

                    for bucket_to_create in buckets_to_create:
                        if bucket_to_create["name"] in bucket_list:
                            self.logger.warning(f"SKIP: Bucket with name {bucket_to_create['name']} is "
                                                f"already present in {self.data['pc_ip']!r}")
                            continue
                        try:
                            response = bucket.create_bucket(os_uuid=os_uuid,
                                                            enable_nfs=bucket_to_create.get("enable_nfs", False),
                                                            bucket_name=bucket_to_create["name"],
                                                            owner_uid=bucket_to_create.get("anonymous_gid",
                                                                                           self.OWNER_UID),
                                                            owner_gid=bucket_to_create.get("anonymous_gid",
                                                                                           self.OWNER_GID),
                                                            file_permission=bucket_to_create.get("file_permission",
                                                                                                 self.FILE_PERMISSION),
                                                            directory_permission=bucket_to_create.get(
                                                                "directory_permission",
                                                                self.DIRECTORY_PERMISSION),
                                                            squash=bucket_to_create.get("squash", "RootSquash"),
                                                            readonly=bucket_to_create.get("readonly", False),
                                                            anonymous_uid=bucket_to_create.get("anonymous_gid",
                                                                                               self.ANONYMOUS_GID),
                                                            anonymous_gid=bucket_to_create.get("anonymous_gid",
                                                                                               self.ANONYMOUS_GID))
                            logger.debug(response)
                        except Exception as e:
                            self.exceptions.append(f"Failed to create Bucket with name {bucket_to_create['name']}: "
                                                   f"{e}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.object_stores:
            return

        # Initial status
        self.results["Create_Buckets"] = {}

        os = ObjectStore(self.pc_session)
        bucket = Buckets(self.pc_session)

        for object_store in self.object_stores:
            os_obj = os.get_entity_by_name(object_store["name"])
            if os_obj:
                os_uuid = os_obj["uuid"]
                bucket_list = []
                for bucket_to_create in object_store.get("buckets", []):
                    try:
                        self.results["Create_Buckets"][bucket_to_create["name"]] = "CAN'T VERIFY"
                        bucket_list = bucket_list or [bucket.get('name') for bucket in bucket.list_buckets(os_uuid)]
                        if bucket_to_create.get("name") in bucket_list:
                            self.results["Create_Buckets"][bucket_to_create["name"]] = "PASS"
                        else:
                            self.results["Create_Buckets"][bucket_to_create["name"]] = "FAIL"
                    except Exception as e:
                        self.logger.debug(e)
                        self.logger.info(
                            f"Exception occurred during the verification of {type(self).__name__!r}")
