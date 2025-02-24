import pytest
from framework.scripts.python.helpers.objects.buckets import Buckets
from framework.scripts.python.helpers.oss_entity_v3 import OssEntityOp
from framework.helpers.rest_utils import RestAPIUtil
from unittest.mock import MagicMock

class TestBuckets:
    @pytest.fixture
    def buckets(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Buckets(session=self.session)

    def test_buckets_init(self, buckets):
        assert buckets.resource_type == "/objectstores"
        assert buckets.session == self.session
        assert isinstance(buckets, Buckets)
        assert isinstance(buckets, OssEntityOp)
        assert buckets.ATTRIBUTES == ["uuid", "name", "storage_usage_bytes", "object_count",
                                      "versioning", "worm", "bucket_notification_state",
                                      "website", "retention_start", "retention_duration_days",
                                      "suspend_versioning", "cors"]
        assert buckets.SHARE_ATTRIBUTES == ["name", "buckets_share"]
        assert buckets.kind == "bucket"
        assert buckets.COMPLETE == "COMPLETE"
        assert buckets.READ == ["READ"]
        assert buckets.WRITE == ["WRITE"]
        assert buckets.READ_WRITE == ["READ", "WRITE"]

    def test_create_bucket(self, mocker, buckets):
        mock_create = mocker.patch.object(Buckets, 'create')
        mock_create.return_value = {"status": "success"}

        response = buckets.create_bucket(os_uuid="os_uuid", bucket_name="bucket_name")
        assert response == {"status": "success"}

        expected_payload = {
            "api_version": "3.0",
            "metadata": {"kind": "bucket"},
            "spec": {
                "name": "bucket_name",
                "description": "",
                "resources": {"features": []}
            }
        }
        mock_create.assert_called_once_with(endpoint="os_uuid/buckets", data=expected_payload)
        
    def test_list_buckets(self, mocker, buckets):
        mock_list = mocker.patch.object(OssEntityOp, 'list')
        mock_list.return_value = [{"name": "bucket1"}, {"name": "bucket2"}]

        response = buckets.list_buckets(os_uuid="os_uuid")
        assert response == [{"name": "bucket1"}, {"name": "bucket2"}]

        mock_list.assert_called_once_with(attributes=buckets.ATTRIBUTES,
            base_path=f"{buckets.__BASEURL__}/{buckets.resource_type}/os_uuid")

    def test_share_bucket(self, mocker, buckets):
        mock_update = mocker.patch.object(Buckets, 'update')
        mock_update.return_value = {"status": "success"}

        response = buckets.share_bucket(os_uuid="os_uuid", bucket_name="bucket_name",
                                        usernames=["user1", "user2"])
        assert response == {"status": "success"}

        expected_payload ={
            "name": "bucket_name",
            "bucket_permissions": [
                {
                    "username": username,
                    "permissions": buckets.READ_WRITE
                } for username in ["user1", "user2"]
            ]
        }
        mock_update.assert_called_once_with(data=expected_payload, endpoint="os_uuid/buckets/bucket_name/share")

    def test_user_list(self, mocker, buckets):
        mock_list = mocker.patch.object(OssEntityOp, 'list')
        mock_list.return_value = [{"buckets_share": {"name":"user1"}}, {"buckets_share":{"name": "user2"}}]

        response = buckets.user_list(os_uuid="os_uuid", bucket_name="bucket_name")
        assert response == [{"name": "user1"}, {"name": "user2"}]

        mock_list.assert_called_once_with(attributes=['name', 'buckets_share'],
            base_path=f"{buckets.__BASEURL__}/{buckets.resource_type}/os_uuid",
            entity_ids=['bucket_name'])
    