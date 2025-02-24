import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.network import Network

class TestNetwork:

    @pytest.fixture
    def network(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Network(session=self.session)

    def test_network_init(self, network):
        '''
        Test that the Network class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert network.resource_type == "/subnets"
        assert network.session == self.session
        assert isinstance(network, Network)
        assert isinstance(network, PcEntity)

    def test_batch_create_network(self, network, mocker):
        subnet_create_payload_list = [{"spec": {"name": "test_subnet"}}]
        mock_batch_create = mocker.patch.object(network.batch_op, 'batch_create', return_value=[{"status": "success"}])

        response = network.batch_create_network(subnet_create_payload_list)

        mock_batch_create.assert_called_once_with(request_payload_list=subnet_create_payload_list)
        assert response == [{"status": "success"}]

    def test_batch_delete_network(self, network, mocker):
        uuid_list = ["uuid1", "uuid2"]
        mock_batch_delete = mocker.patch.object(network.batch_op, 'batch_delete', return_value=[{"status": "success"}])

        response = network.batch_delete_network(uuid_list)

        mock_batch_delete.assert_called_once_with(entity_list=uuid_list)
        assert response == [{"status": "success"}]

    def test_get_uuid_by_name(self, network, mocker):
        cluster_name = "test_cluster"
        subnet_name = "test_subnet"
        expected_uuid = "uuid1"
        mock_get_uuid_by_name = mocker.patch.object(PcEntity, 'get_uuid_by_name', return_value=expected_uuid)

        uuid = network.get_uuid_by_name(cluster_name, subnet_name)

        mock_get_uuid_by_name.assert_called_once_with(subnet_name, filter="cluster_name==test_cluster;name==test_subnet")
        assert uuid == expected_uuid

    def test_create_subnet_payload(self):
        kwargs = {
            "name": "test_subnet",
            "subnet_type": "VLAN",
            "vlan_id": 10,
            "vs_uuid": "vs_uuid",
            "vpc_id": "vpc_uuid",
            "ip_config": {
                "network_ip": "192.168.1.0",
                "network_prefix": 24,
                "default_gateway_ip": "192.168.1.1",
                "pool_list": [{"range": "192.168.1.2 192.168.1.254"}]
            },
            "cluster_uuid": "cluster_uuid",
            "is_external": True,
            "enable_nat": False
        }
        expected_payload = {
            "spec": {
                "name": "test_subnet",
                "resources": {
                    "subnet_type": "VLAN",
                    "vlan_id": 10,
                    "virtual_switch_uuid": "vs_uuid",
                    "vpc_reference": {
                        "kind": "vpc",
                        "uuid": "vpc_uuid"
                    },
                    "virtual_network_reference": {
                        "kind": "virtual_network",
                        "uuid": "vpc_uuid"
                    },
                    "is_external": True,
                    "enable_nat": False,
                    "ip_config": {
                        "subnet_ip": "192.168.1.0",
                        "prefix_length": 24,
                        "default_gateway_ip": "192.168.1.1",
                        "dhcp_options": {},
                        "pool_list": [{"range": "192.168.1.2 192.168.1.254"}]
                    }
                },
                "cluster_reference": {
                    "kind": "cluster",
                    "uuid": "cluster_uuid"
                }
            },
            "metadata": {
                "kind": "subnet",
                "name": "test_subnet"
            },
            "api_version": "3.1.0"
        }

        payload = Network.create_subnet_payload(**kwargs)

        assert payload == expected_payload

    def test_create_pc_subnet_payload(self, network):
        kwargs = {
            "name": "test_subnet",
            "vlan_id": 10,
            "subnet_ip": "192.168.1.0",
            "prefix_length": 24,
            "default_gateway_ip": "192.168.1.1",
            "pool_list": [{"range": "192.168.1.2 192.168.1.254"}],
            "cluster_uuid": "cluster_uuid"
        }
        expected_payload = {
            "spec": {
                "name": "test_subnet",
                "resources": {
                    "subnet_type": "VLAN",
                    "vlan_id": 10,
                    "ip_config": {
                        "subnet_ip": "192.168.1.0",
                        "prefix_length": 24,
                        "default_gateway_ip": "192.168.1.1",
                        "dhcp_options": {},
                        "pool_list": [{"range": "192.168.1.2 192.168.1.254"}]
                    }
                },
                "cluster_reference": {
                    "kind": "cluster",
                    "uuid": "cluster_uuid"
                }
            },
            "metadata": {
                "kind": "subnet",
                "name": "test_subnet"
            },
            "api_version": "3.1.0"
        }

        payload = network.create_pc_subnet_payload(
            name=kwargs['name'],
            vlan_id=kwargs['vlan_id'],
            ip_config={
                "network_ip": kwargs['subnet_ip'],
                "network_prefix": kwargs['prefix_length'],
                "default_gateway_ip": kwargs['default_gateway_ip'],
                "pool_list": kwargs['pool_list']
            },
            cluster_uuid=kwargs['cluster_uuid']
        )

        assert payload == expected_payload