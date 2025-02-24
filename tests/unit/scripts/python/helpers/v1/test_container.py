import pytest
from unittest.mock import MagicMock
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.container import Container
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from framework.scripts.python.helpers.v1.storage_pool import StoragePool


class TestContainer:
    @pytest.fixture
    def container(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Container(session=self.session)

    def test_container_init(self, container):
        assert container.resource_type == "/containers"
        assert container.session == self.session
        assert isinstance(container, Container)
        assert isinstance(container, PeEntityV1)

    def test_get_json_for_create(self, container, mocker):
        container_name = "test_container"
        storage_pool_uuid = "12345"
        advertisedCapacity_in_gb = 100
        reserved_in_gb = 2
        replication_factor = 2
        compression_enabled = True
        compression_delay_in_secs = 10
        erasure_code = "ON"
        finger_print_on_write = "ON"
        on_disk_dedup = "ON"

        mocker.patch.object(StoragePool, "read", return_value=[{"storagePoolUuid": storage_pool_uuid}])

        json_data = container.get_json_for_create(
            name=container_name,
            storage_pool_uuid=storage_pool_uuid,
            advertisedCapacity_in_gb=advertisedCapacity_in_gb,
            reserved_in_gb=reserved_in_gb,
            replication_factor=replication_factor,
            compression_enabled=compression_enabled,
            compression_delay_in_secs=compression_delay_in_secs,
            erasure_code=erasure_code,
            finger_print_on_write=finger_print_on_write,
            on_disk_dedup=on_disk_dedup
        )

        excepted_json_data = {
            "name": container_name,
            "storagePoolUuid": storage_pool_uuid,
            "advertisedCapacity": advertisedCapacity_in_gb * 1024 * 1024 * 1024,
            "compressionEnabled": compression_enabled,
            "compressionDelayInSecs": compression_delay_in_secs,
            "erasureCode": erasure_code,
            "fingerPrintOnWrite": finger_print_on_write,
            "onDiskDedup": on_disk_dedup,
            "nfsWhitelistAddress": [],
            "replicationFactor": str(replication_factor),
            "totalExplicitReservedCapacity": reserved_in_gb * 1024 * 1024 * 1024,
        }

        assert json_data == excepted_json_data
    
    def test_get_json_for_create_no_storage_pool(self, container, mocker):
        mocker.patch.object(StoragePool, "read", return_value=[])

        with pytest.raises(ValueError):
            container.get_json_for_create(name="test_container")

    def test_create(self, container, mocker):
        payload = {
            "name": "test_container",
            "storage_pool_uuid": "12345",
            "advertised_capacity": 100,
            "replication_factor": 2,
            "compression_enabled": True,
            "compression_delay_in_secs": 10,
            "erasure_code": "ON",
            "finger_print_on_write": "ON",
            "on_disk_dedup": "ON"
        }
        
        mock_create = mocker.patch.object(PeEntityV1, "create")
        container.create(**payload)
        mock_create.assert_called_once_with(data=container.get_json_for_create(**payload))

