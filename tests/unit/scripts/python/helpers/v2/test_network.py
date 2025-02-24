import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v2.network import Network
from framework.scripts.python.helpers.pe_entity_v2 import PeEntityV2
from framework.scripts.python.helpers.v1.virtual_switch import VirtualSwitch
from unittest.mock import MagicMock

class TestNetwork:
    @pytest.fixture
    def network(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Network(session=self.session)
    
    def test_network_init(self, network):
        assert network.resource_type == "/networks"
        assert network.session == self.session
        assert isinstance(network, Network)
        assert isinstance(network, PeEntityV2)
        
    def test_get_json_for_create(self, network, mocker):
        network_name = "test_network"
        vlan_id = 100
        virtual_switch = "test_switch"
        ip_config = {
            "network_ip": "192.168.10.0",
            "network_prefix": 24,
            "default_gateway_ip": "192.168.10.1",
            "pool_list": [{"range": "192.168.10.20 192.168.10.250"}],
            "dhcp_options": {"domain_name_server_list": ["10.10.10.10","20.20.20.20"]},
            "dhcp_server_address": "9.9.9.9",
            #TODO :Add dhcp_options
        }
        mocker.patch.object(VirtualSwitch, "get_vs_uuid", return_value="test_uuid")
                
        payload_ip_config = {
            'network_address': ip_config['network_ip'],
            'prefix_length': ip_config['network_prefix'],
            'default_gateway': ip_config['default_gateway_ip'],
            'pool': ip_config['pool_list'],
            'dhcp_options': ip_config['dhcp_options'],
            'dhcp_server_address': {"ip": ip_config['dhcp_server_address']}
        }

        expected_payload = {
            'name': network_name, 'vlan_id': vlan_id,
            'virtual_switch_uuid': 'test_uuid',
            'ip_config': {
                'network_address': ip_config['network_ip'],
                'prefix_length': ip_config['network_prefix'],
                'default_gateway': ip_config['default_gateway_ip'],
                'dhcp_options': {
                    'domain_name_servers': '10.10.10.10,20.20.20.20'
                    },
                'pool': ip_config['pool_list']
                }
            }
        payload = network.get_json_for_create(
            name=network_name, vlan_id=vlan_id, virtual_switch=virtual_switch, ip_config=ip_config
        )
        #print(expected_payload['ip_config'])
        assert payload == expected_payload
        
    def test_create(self, network, mocker):
        payload = {"name": "test_network", "vlan_id": 100, "virtual_switch": "test_switch", "ip_config": {}}
        mocker.patch.object(VirtualSwitch, "get_vs_uuid", return_value="test_uuid")
        mock_create = mocker.patch.object(PeEntityV2, "create")
        network.create(**payload)
        mock_create.assert_called_once_with(data=network.get_json_for_create(**payload))
        