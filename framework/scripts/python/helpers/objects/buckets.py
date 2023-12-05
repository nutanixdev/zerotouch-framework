from typing import List, Dict, Optional
from framework.helpers.rest_utils import RestAPIUtil
from ..oss_entity_v3 import OssEntityOp


class Buckets(OssEntityOp):
    """
    Class to handle all the /objectstores REST API endpoints
    """
    ATTRIBUTES = [
        "uuid",
        "name",
        "storage_usage_bytes",
        "object_count",
        "versioning",
        "worm",
        "bucket_notification_state",
        "website",
        "retention_start",
        "retention_duration_days",
        "suspend_versioning",
        "cors"
    ]
    SHARE_ATTRIBUTES = ["name", "buckets_share"]
    kind = "bucket"
    COMPLETE = "COMPLETE"
    READ = ["READ"]
    WRITE = ["WRITE"]
    READ_WRITE = ["READ", "WRITE"]

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/objectstores"
        super(Buckets, self).__init__(session=session)

    def create_bucket(self, os_uuid: str, bucket_name: str, **kwargs) -> Dict:
        """
        Create buckets under given object store
        Args:
          os_uuid(str): The uuid of the objectstore
          bucket_name(str): The name of the bucket
          kwargs(dict):
            optional
        Returns:
          dict: API response
        """
        endpoint = f"{os_uuid}/buckets"
        payload = {
            "api_version": "3.0",
            "metadata": {"kind": self.kind},
            "spec": {
                "name": bucket_name,
                "description": "",
                "resources": {"features": []}}}

        # this will get overwritten when there is an expiration rule
        # on versioned object.
        if kwargs.get('expiration', False):
            payload['spec']['resources']['lifecycle_configuration'] = {"Rule": [{
                "ID": "ntnx-frontend-emptyprefix-rule",
                "Filter": {},
                "Status": "Enabled",
                "Expiration": {"Days": kwargs.get('expiration')}}]}

        if kwargs.get('enable_versioning', False):
            payload['spec']['resources']['features'].append('VERSIONING')
            if kwargs.get('NoncurrentVersionExpiration', False):
                payload['spec']['resources']['lifecycle_configuration'] = {"Rule": [{
                    "ID": "ntnx-frontend-emptyprefix-rule",
                    "Filter": {},
                    "Status": "Enabled",
                    "NoncurrentVersionExpiration": {
                        "NoncurrentDays": kwargs.get('NoncurrentVersionExpiration')}}]}
                if kwargs.get('Expiration', False):
                    payload['spec']['resources']['lifecycle_configuration']['Rule'][0][
                        "Expiration"] = {"Days": kwargs.get('Expiration')}

        if kwargs.get('enable_worm', False):
            payload['spec']['resources']['features'].append('WORM')
            if kwargs.get('worm_retention_days', False):
                payload['spec']['resources']['worm_retention_days'] = \
                    kwargs.get('worm_retention_days')

        if kwargs.get("enable_nfs", False):
            payload['spec']['resources']["nfs_configuration"] = {
                "owner": {"UID": kwargs.get("owner_uid"),
                          "GID": kwargs.get("owner_gid")},
                "permissions": {"file": kwargs.get("file_permission"),
                                "directory": kwargs.get("directory_permission")},
                "squash": kwargs.get("squash"),
                "readonly": kwargs.get("readonly"),
                "anonymous": {"UID": kwargs.get("anonymous_uid"),
                              "GID": kwargs.get("anonymous_gid")}
            }

        return self.create(
            endpoint=endpoint,
            data=payload
        )

    def list_buckets(self, os_uuid: str) -> List:
        """
        List all the buckets of given objectstore
        Args:
          os_uuid(str): The uuid of given objectstore
        Returns:
          list: The list of buckets
        """

        entities = super().list(
            attributes=self.ATTRIBUTES,
            base_path=f"{self.__BASEURL__}/{self.resource_type}/{os_uuid}")
        return [entity for entity in entities]

    def share_bucket(self, os_uuid: str, bucket_name: str, usernames: List,
                     permission: Optional[List] = None) -> Dict:
        """
        Method to share the bucket with users.
        Args:
          os_uuid(str): The uuid of given objectstore
          bucket_name(str): Name of the bucket
          usernames(str): list of usernames. username should be in email format
          permission(list): The permission
        Returns:
          response(dict): Response of get bucket API call.
        """
        endpoint = f"{os_uuid}/buckets/{bucket_name}/share"
        payload = {
            "name": bucket_name,
            "bucket_permissions": [
                {
                    "username": username,
                    "permissions": permission or self.READ_WRITE
                } for username in usernames
            ]
        }
        return self.update(data=payload, endpoint=endpoint)

    def user_list(self, os_uuid: str, bucket_name: str) -> List[str]:
        """
        Method to get bucket users
        Args:
          os_uuid(str): The uuid of given objectstore
          bucket_name(str): The name of the bucket
        Returns:
          response(List): parsed API response.
        """
        entities = super().list(
            attributes=self.SHARE_ATTRIBUTES,
            base_path=f"{self.__BASEURL__}/{self.resource_type}/{os_uuid}",
            entity_ids=[bucket_name]
        )
        return [entity["buckets_share"] for entity in entities]
