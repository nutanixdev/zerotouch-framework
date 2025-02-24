import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.objects.objectstore import ObjectStore
from framework.scripts.python.helpers.oss_entity_v3 import OssEntityOp
from framework.scripts.python.helpers.v3.cluster import Cluster

class TestObjectStore:
    @pytest.fixture
    def object_store(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return ObjectStore(session = self.session)
    
    def test_object_store_init(self, object_store):
        assert object_store.resource_type == "/objectstores"
        assert object_store.session == self.session
        assert isinstance(object_store, ObjectStore)
        assert isinstance(object_store, OssEntityOp)

    def test_get_entity_by_name(self, mocker, object_store):
        mock_list = mocker.patch.object(ObjectStore, 'list')
        mock_list.return_value = [
            {"name": "entity1", "uuid": "uuid1"},
            {"name": "entity2", "uuid": "uuid2"}
        ]

        response = object_store.get_entity_by_name("entity1")
        assert response == {"name": "entity1", "uuid": "uuid1"}
        mock_list.assert_called_once()
        
        response = object_store.get_entity_by_name("entity3")
        assert response == []
        mock_list.assert_called()

    def test_list(self, mocker, object_store):
        mock_list = mocker.patch.object(OssEntityOp, 'list')
        mock_list.return_value = [
            {"name": "entity1", "uuid": "uuid1"},
            {"name": "entity2", "uuid": "uuid2"}
        ]

        response = object_store.list()
        assert response == [
            {"name": "entity1", "uuid": "uuid1"},
            {"name": "entity2", "uuid": "uuid2"}
        ]
        mock_list.assert_called_once_with(attributes=object_store.ATTRIBUTES)

    def test_get_payload(self, mocker, object_store):
        mock_network = mocker.patch('framework.scripts.python.helpers.objects.objectstore.Network')
        mock_cluster = mocker.patch('framework.scripts.python.helpers.objects.objectstore.PcCluster')
        mock_cluster_instance = mock_cluster.return_value
        mock_cluster_instance.get_uuid_by_name.return_value = "cluster_uuid"
        mock_network_instance = mock_network.return_value
        mock_network_instance.get_uuid_by_name.return_value = "network_uuid"

        kwargs = {
            "name": "test_objectstore",
            "domain": "test_domain",
            "cluster": "test_cluster",
            "network": "test_network",
            "static_ip_list": ["ip1", "ip2", "ip3", "ip4"]
        }
        payload = object_store.get_payload(**kwargs)
        expected_payload = {
            "api_version": "3.0",
            "metadata": {"kind": "objectstore"},
            "spec": {
                "name": "test_objectstore",
                "description": "",
                "resources": {
                    "domain": "test_domain",
                    "num_worker_nodes": 3,
                    "cluster_reference": {"kind": "cluster", "uuid": "cluster_uuid"},
                    "buckets_infra_network_dns": "ip1",
                    "buckets_infra_network_vip": "ip2",
                    "buckets_infra_network_reference": {"kind": "subnet", "uuid": "network_uuid"},
                    "client_access_network_reference": {"kind": "subnet", "uuid": "network_uuid"},
                    "aggregate_resources": {
                        "total_vcpu_count": 0,
                        "total_memory_size_mib": 0,
                        "total_capacity_gib": 0
                    },
                    "client_access_network_ip_list": ["ip3", "ip4"]
                }
            }
        }

        assert payload == expected_payload


    def test_create(self, mocker, object_store):
        mock_create = mocker.patch.object(OssEntityOp, 'create')
        mock_network = mocker.patch('framework.scripts.python.helpers.objects.objectstore.Network')
        mock_cluster = mocker.patch('framework.scripts.python.helpers.objects.objectstore.PcCluster')
        mock_cluster_instance = mock_cluster.return_value
        mock_cluster_instance.get_uuid_by_name.return_value = "cluster_uuid"
        mock_network_instance = mock_network.return_value
        mock_network_instance.get_uuid_by_name.return_value = "network_uuid"
        mock_create.return_value = {"status": "success"}

        kwargs = {
            "name": "test_objectstore",
            "domain": "test_domain",
            "cluster": "test_cluster",
            "network": "test_network",
            "static_ip_list": ["ip1", "ip2", "ip3", "ip4"]
        }

        response = object_store.create(**kwargs)
        expected_payload = {
            "api_version": "3.0",
            "metadata": {"kind": "objectstore"},
            "spec": {
                "name": "test_objectstore",
                "description": "",
                "resources": {
                    "domain": "test_domain",
                    "num_worker_nodes": 3,
                    "cluster_reference": {"kind": "cluster", "uuid": "cluster_uuid"},
                    "buckets_infra_network_dns": "ip1",
                    "buckets_infra_network_vip": "ip2",
                    "buckets_infra_network_reference": {"kind": "subnet", "uuid": "network_uuid"},
                    "client_access_network_reference": {"kind": "subnet", "uuid": "network_uuid"},
                    "aggregate_resources": {
                        "total_vcpu_count": 0,
                        "total_memory_size_mib": 0,
                        "total_capacity_gib": 0
                    },
                    "client_access_network_ip_list": ["ip3", "ip4"]
                }
            }
        }

        mock_create.assert_called_once_with(data=expected_payload)
        assert response == {"status": "success"}
