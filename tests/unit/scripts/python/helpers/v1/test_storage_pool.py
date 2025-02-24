import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.storage_pool import StoragePool
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestStoragePool:
    @pytest.fixture
    def storage_pool(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return StoragePool(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)
    
    def test_storage_pool_init(self, storage_pool):
        assert storage_pool.resource_type == "/storage_pools"
        assert storage_pool.session == self.session
        assert storage_pool.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(storage_pool, StoragePool)
        assert isinstance(storage_pool, PeEntityV1)