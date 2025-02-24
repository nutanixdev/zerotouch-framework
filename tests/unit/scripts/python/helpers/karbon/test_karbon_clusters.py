import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.karbon.karbon_clusters import KarbonClusterV1, KarbonCluster, Karbon
from framework.helpers.rest_utils import RestAPIUtil
from framework.helpers.helper_functions import read_creds

@pytest.fixture
def session():
    return MagicMock(spec=RestAPIUtil)

@pytest.fixture
def karbon_cluster(session):
    data = {"credential_store": {}}
    return KarbonClusterV1(session, data)

class TestKarbonClusterV1:
    def test_karbon_cluster_init(self, karbon_cluster):
        assert karbon_cluster.resource_type == "/v1/k8s/clusters"
        assert karbon_cluster.kind == "cluster"
        assert karbon_cluster.session is not None


    def test_get_payload(self, mocker, karbon_cluster):
        MockCluster = mocker.patch("framework.scripts.python.helpers.karbon.karbon_clusters.Cluster")
        MockNetwork = mocker.patch("framework.scripts.python.helpers.karbon.karbon_clusters.Network")

        cluster_spec = {
            "name": "test_cluster",
            "cluster_type": "PROD",
            "cluster": {"name": "test_cluster_name"},
            "node_subnet": {"name": "test_subnet"},
            "control_plane_virtual_ip": "192.168.1.2",
            "host_os": "CentOS"
        }

        mock_pc_cluster = MockCluster.return_value
        mock_pc_cluster.name_uuid_map = {"test_cluster_name": "test_cluster_uuid"}
        mock_subnet = MockNetwork.return_value
        mock_subnet.get_uuid_by_name.return_value = "test_subnet_uuid"

        mock_get_spec = mocker.patch.object(Karbon, 'get_spec')
        mock_get_spec.return_value = ({"name": "test_cluster", "metadata": {"api_version": "v1.0.0"}},None)
        payload = karbon_cluster.get_payload(cluster_spec, data={})
        assert payload == {"name": "test_cluster", "metadata": {"api_version": "v1.0.0"}}
        mock_pc_cluster.get_pe_info_list.assert_called_once()
        mock_subnet.get_uuid_by_name.assert_called_once_with(
            cluster_name="test_cluster_name", subnet_name="test_subnet"
        )
        mock_get_spec.assert_called_once_with(params=cluster_spec)

    def test_get_default_spec(self, karbon_cluster):
        spec = karbon_cluster._get_default_spec()
        expected_spec = {
            "name": "",
            "metadata": {"api_version": "v1.0.0"},
            "version": "",
            "cni_config": {},
            "etcd_config": {},
            "masters_config": {"single_master_config": {}},
            "storage_class_config": {},
            "workers_config": {},
        }
        assert spec == expected_spec

    def test_build_spec_name(self, karbon_cluster):
        payload = {}
        value = "test_cluster"
        updated_payload, error = karbon_cluster._build_spec_name(payload, value)
        assert updated_payload["name"] == value
        assert error is None

    def test_build_spec_k8s_version(self, karbon_cluster):
        payload = {}
        value = "1.18.6"
        updated_payload, error = karbon_cluster._build_spec_k8s_version(payload, value)
        assert updated_payload["version"] == value
        assert error is None

    def test_build_spec_cni(self, karbon_cluster):
        payload = {}
        config = {
            "node_cidr_mask_size": 24,
            "service_ipv4_cidr": "10.96.0.0/12",
            "pod_ipv4_cidr": "192.168.0.0/16",
            "network_provider": "Calico"
        }
        updated_payload, error = karbon_cluster._build_spec_cni(payload, config)
        expected_cni = {
            "node_cidr_mask_size": 24,
            "service_ipv4_cidr": "10.96.0.0/12",
            "pod_ipv4_cidr": "192.168.0.0/16",
            "calico_config": {
                "ip_pool_configs": [{"cidr": "192.168.0.0/16"}]
            }
        }
        assert updated_payload["cni_config"] == expected_cni
        assert error is None

    def test_build_spec_node_configs(self, mocker, karbon_cluster):
        mock_generate_resource_spec = mocker.patch.object(
            karbon_cluster, '_generate_resource_spec'
        )

        mock_generate_resource_spec.side_effect = [
            ({"num_instances": 1,"single_master_config":{}}, None),
            ({"num_instances": 2, "single_master_config":{}}, None)
        ]

        payload = {"masters_config": {}, "workers_config": {}}
        config = {
            "masters": {"cpu": 4, "memory_gb": 16, "disk_gb": 100, "num_instances": 2},
            "workers": {"cpu": 2, "memory_gb": 8, "disk_gb": 50, "num_instances": 3}
        }

        karbon_cluster.cluster_type = "PROD"
        karbon_cluster.control_plane_virtual_ip = "192.168.1.2"
        updated_payload, error = karbon_cluster._build_spec_node_configs(payload, config)
        
        expected_payload = {
            'masters_config': {
                'node_pools': [{'num_instances': 1, 'single_master_config': {}}]},
            'workers_config': {
                'node_pools': [{'num_instances': 2, 'single_master_config': {}}]}
            }


        assert updated_payload == expected_payload
        assert error is None
        mock_generate_resource_spec.assert_any_call(
            config["masters"], "master"
        )
        mock_generate_resource_spec.assert_any_call(
            config["workers"], "worker"
        )

        # Test case : Missing control_plane_virtual_ip
        mock_generate_resource_spec.reset_mock()
        mock_generate_resource_spec.side_effect = None
        mock_generate_resource_spec.return_value = ({"num_instances": 2}, None)

        payload = {"masters_config": {}, "workers_config": {}}
        config = {
            "masters": {"cpu": 4, "memory_gb": 16, "disk_gb": 100, "num_instances": 2}
        }

        karbon_cluster.cluster_type = "PROD"
        karbon_cluster.control_plane_virtual_ip = None
        updated_payload, error = karbon_cluster._build_spec_node_configs(payload, config)

        assert updated_payload is None
        assert error == "control_plane_virtual_ip is required if the number of master nodes is 2 or cluster_type is 'PROD'."
        mock_generate_resource_spec.assert_called_once_with(
            config["masters"], "master"
        )

        # Test case : cluster_type is DEV
        mock_generate_resource_spec.reset_mock()
        mock_generate_resource_spec.return_value = ({"num_instances": 1}, None)

        payload = {"masters_config": {}, "workers_config": {}}
        config = {
            "masters": {"cpu": 4, "memory_gb": 16, "disk_gb": 100, "num_instances": 1}
        }

        karbon_cluster.cluster_type = "DEV"
        karbon_cluster.control_plane_virtual_ip = None
        updated_payload, error = karbon_cluster._build_spec_node_configs(payload, config)

        expected_payload = {
            "masters_config": {
                "node_pools": [{"num_instances": 1}]
            },
            "workers_config": {}
        }
        assert updated_payload == expected_payload
        assert error is None
        mock_generate_resource_spec.assert_called_once_with(
            config["masters"], "master"
        )

        
    
    def test_build_spec_storage_class(self, mocker, karbon_cluster):
        mock_read_creds = mocker.patch("framework.scripts.python.helpers.karbon.karbon_clusters.read_creds")
        mock_read_creds.return_value = ("username", "password")
        payload = {}
        config = {
            "pe_credential": "credential_name",
            "default_storage_class": True,
            "name": "test_storage_class",
            "reclaim_policy": "Delete",
            "storage_container": "test_container",
            "file_system": "ext4",
            "flash_mode": True
        }
        karbon_cluster.cluster_uuid = "test_cluster_uuid"
        updated_payload, error = karbon_cluster._build_spec_storage_class(payload, config)
        expected_storage_class = {
            "default_storage_class": True,
            "name": "test_storage_class",
            "reclaim_policy": "Delete",
            "volumes_config": {
                "prism_element_cluster_uuid": "test_cluster_uuid",
                "username": "username",
                "password": "password",
                "storage_container": "test_container",
                "file_system": "ext4",
                "flash_mode": True
            }
        }
        assert updated_payload["storage_class_config"] == expected_storage_class
        assert error is None

    def test_validate_resources(self, karbon_cluster):
        resources = {"num_instances": 3}
        resource_type = "etcd"
        validated_resources, error = karbon_cluster.validate_resources(resources, resource_type)
        assert validated_resources == resources
        assert error is None

        resources = {"num_instances": 4}
        validated_resources, error = karbon_cluster.validate_resources(resources, resource_type)
        assert validated_resources is None
        assert error == "value of etcd.num_instances must be 1, 3 or 5"

class TestKarbonCluster:
    @pytest.fixture
    def karbon_cluster(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return KarbonCluster(session = self.session)

    def test_karbon_cluster_init(self, karbon_cluster):
        assert karbon_cluster.resource_type == "/acs/k8s/cluster/"
        assert karbon_cluster.kind == "cluster"
        assert karbon_cluster.session == self.session

    def test_list_clusters(self, mocker, karbon_cluster):
        mock_list = mocker.patch.object(Karbon,'list')
        clusters = karbon_cluster.list()
        mock_list.assert_called_once_with(data={})
        