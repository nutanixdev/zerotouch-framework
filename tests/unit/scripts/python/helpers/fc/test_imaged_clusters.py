import pytest
from framework.scripts.python.helpers.fc.imaged_clusters import ImagedCluster
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.fc_entity import FcEntity
from unittest.mock import MagicMock

class TestImagedCluster:
    @pytest.fixture
    def imaged_cluster(self, mocker):
        self.mock_pc_session = MagicMock(spec=RestAPIUtil)
        return ImagedCluster(self.mock_pc_session)
    
    def test_imaged_cluster_init(self, imaged_cluster):
        assert isinstance(imaged_cluster, ImagedCluster)
        assert isinstance(imaged_cluster, FcEntity)
        assert imaged_cluster.resource_type == "/imaged_clusters"
        assert imaged_cluster.build_spec_methods == {
            "cluster_external_ip": imaged_cluster._build_spec_cluster_exip,
            "common_network_settings": imaged_cluster._build_spec_common_network_settings,
            "hypervisor_isos": imaged_cluster._build_spec_hypervisor_iso_details,
            "storage_node_count": imaged_cluster._build_spec_storage_node_count,
            "redundancy_factor": imaged_cluster._build_spec_redundancy_factor,
            "cluster_name": imaged_cluster._build_spec_cluster_name,
            "aos_package_url": imaged_cluster._build_spec_aos_package_url,
            "cluster_size": imaged_cluster._build_spec_cluster_size,
            "aos_package_sha256sum": imaged_cluster._build_spec_aos_package_sha256sum,
            "timezone": imaged_cluster._build_spec_timezone,
            "nodes_list": imaged_cluster._build_spec_nodes_list,
            "skip_cluster_creation": imaged_cluster._build_spec_skip_cluster_creation,
            "filters": imaged_cluster._build_spec_filters,
        }
    
    def test_get_default_spec(self, imaged_cluster):
        assert imaged_cluster._get_default_spec() == {
            "cluster_external_ip": "",
            "common_network_settings": {},
            "redundancy_factor": 2,
            "cluster_name": "",
            "aos_package_url": None,
            "hypervisor_isos": [],
            "nodes_list": [],
        }
    
    def test_build_spec_cluster_exip(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_cluster_exip(payload, value) == ({"cluster_external_ip": "test_value"}, None)
        
    def test_build_spec_storage_node_count(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_storage_node_count(payload, value) == ({"storage_node_count": "test_value"}, None)
    
    def test_build_spec_redundancy_factor(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_redundancy_factor(payload, value) == ({"redundancy_factor": "test_value"}, None)
    
    def test_build_spec_cluster_name(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_cluster_name(payload, value) == ({"cluster_name": "test_value"}, None)
        
    def test_build_spec_aos_package_url(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_aos_package_url(payload, value) == ({"aos_package_url": "test_value"}, None)
        
    def test_build_spec_cluster_size(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_cluster_size(payload, value) == ({"cluster_size": "test_value"}, None)
        
    def test_build_spec_aos_package_sha256sum(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_aos_package_sha256sum(payload, value) == ({"aos_package_sha256sum": "test_value"}, None)
    
    def test_build_spec_timezone(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_timezone(payload, value) == ({"timezone": "test_value"}, None)
    
    def test_build_spec_skip_cluster_creation(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_skip_cluster_creation(payload, value) == ({"skip_cluster_creation": "test_value"}, None)
    
    def test_build_spec_common_network_settings(self, imaged_cluster):
        payload = {}
        value = {}
        assert imaged_cluster._build_spec_common_network_settings(payload, value) == ({"common_network_settings": {}}, None)
        
    def test_build_spec_hypervisor_iso_details(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_hypervisor_iso_details(payload, value) == ({"hypervisor_isos": "test_value"}, None)
        
    def test_build_spec_nodes_list(self, imaged_cluster):
        node_details = [
            {
                "cvm_gateway": "test_gateway",
                "ipmi_netmask": "test_netmask",
                "ipmi_gateway": "test_ipmi_netmask"
             }
            ]
        
        payload = {}
        expected_payload = {
            "nodes_list": [
                {
                    "cvm_gateway": "test_gateway",
                    "ipmi_netmask": "test_netmask",
                    "ipmi_gateway": "test_ipmi_netmask"
                }
            ]
        }
        print(imaged_cluster._build_spec_nodes_list(payload, node_details))
        print(("^^^^"))
        assert imaged_cluster._build_spec_nodes_list(payload, node_details) == (expected_payload, None)
        
    def test_build_spec_filters(self, imaged_cluster):
        payload = {}
        value = "test_value"
        assert imaged_cluster._build_spec_filters(payload, value) == ({"filters": "test_value"}, None)
    
    def test_get_default_hypervisor_iso_details(self, imaged_cluster):
        isodetails = {
            "hyperv_sku": "test_sku",
            "url": "test_url",
            "hypervisor_type": "test_type",
            "hyperv_product_key": "test_key",
            "sha256sum": "test_sha256sum"
        }
        assert imaged_cluster._get_default_hypervisor_iso_details(isodetails) == {
            "hyperv_sku": "test_sku",
            "url": "test_url",
            "hypervisor_type": "test_type",
            "hyperv_product_key": "test_key",
            "sha256sum": "test_sha256sum",
        }
    
    def test_get_default_network_settings(self, imaged_cluster):
        cnsettings = {
            "cvm_dns_servers": ["test_dns"],
            "hypervisor_dns_servers": ["test_dns"],
            "cvm_ntp_servers": ["test_ntp"],
            "hypervisor_ntp_servers": ["test_ntp"],
        }
        assert imaged_cluster._get_default_network_settings(cnsettings) == {
            "cvm_dns_servers": ["test_dns"],
            "hypervisor_dns_servers": ["test_dns"],
            "cvm_ntp_servers": ["test_ntp"],
            "hypervisor_ntp_servers": ["test_ntp"],
        }
        
    def test_get_default_nodes_spec(self, imaged_cluster):
        spec = {
            "cvm_gateway": "test_gateway",
            "ipmi_netmask": "test_netmask",
            "ipmi_gateway": "test_ipmi_netmask"
        }
        
        assert imaged_cluster._get_default_nodes_spec(spec) == {
            "cvm_gateway": "test_gateway",
            "ipmi_netmask": "test_netmask",
            "ipmi_gateway": "test_ipmi_netmask",
        }
    
    def test_get_aos_ahv_spec(self, imaged_cluster):
        test_imaging_params = {
            "aos_url": "http://test_url",
            "hypervisor_type": "kvm",
            "hypervisor_url": "http://test_url",
            
        }
        assert imaged_cluster.get_aos_ahv_spec(test_imaging_params) == {
            "aos_package_url": "http://test_url",
            "hypervisor_isos": [
                {
                    "hypervisor_type": "kvm",
                    "url": "http://test_url",  
                }]
            }
        test_imaging_params.pop("hypervisor_url")
        assert imaged_cluster.get_aos_ahv_spec(test_imaging_params) == {
            "aos_package_url": "http://test_url",
            "hypervisor_isos": []
        }
        
    def test_update_node_details(self, imaged_cluster):
        node_details_list = [
            {   
                "aos_version": "6.5.1",
                "cvm_ip": "test_gateway",
                "ipmi_netmask": "test_netmask",
                "ipmi_gateway": "test_ipmi_netmask",
                "ipmi_ip": "test_ipmi_ip",
                "node_serial": "test1",
                "imaged_node_uuid": "test_uuid1",
             },
            {   
                "aos_version": "6.5.1",
                "cvm_ip": "test_gateway",
                "ipmi_netmask": "test_netmask",
                "ipmi_gateway": "test_ipmi_netmask",
                "ipmi_ip": "test_ipmi_ip",
                "node_serial": "test2",
                "imaged_node_uuid": "test_uuid2",
             }
            ]
        cluster_info = {
            "use_existing_network_settings": False,
            "re-image": True,
            "imaging_parameters": {
                "hypervisor_type": "kvm",
            },
            "cvm_ram": 12,
        }
        updated_node_details_list = imaged_cluster.update_node_details(node_details_list, cluster_info)
        assert updated_node_details_list == [
            {
                "aos_version": "6.5.1",
                "cvm_ip": "test_gateway",
                "cvm_ram_gb": 12,
                "ipmi_netmask": "test_netmask",
                "ipmi_gateway": "test_ipmi_netmask",
                "ipmi_ip": "test_ipmi_ip",
                "node_serial": "test1",
                "imaged_node_uuid": "test_uuid1",
                "rdma_passthrough": False,
                "hypervisor_type": "kvm",
                "image_now": True,
                "cvm_ram_gb": 12,
                "use_existing_network_settings": False
            },
            {
                "aos_version": "6.5.1",
                "cvm_ip": "test_gateway",
                "cvm_ram_gb": 12,
                "ipmi_netmask": "test_netmask",
                "ipmi_gateway": "test_ipmi_netmask",
                "ipmi_ip": "test_ipmi_ip",
                "node_serial": "test2",
                "imaged_node_uuid": "test_uuid2",
                "rdma_passthrough": False,
                "hypervisor_type": "kvm",
                "image_now": True,
                "cvm_ram_gb": 12,
                "use_existing_network_settings": False
            }
        ]
        
        cluster_info["use_existing_network_settings"] = True
        updated_node_details_list = imaged_cluster.update_node_details(node_details_list, cluster_info)
        assert updated_node_details_list == [
            {
                "aos_version": "6.5.1",
                "cvm_ip": "test_gateway",
                "cvm_ram_gb": 12,
                "hypervisor_type": "kvm",
                "node_serial": "test1",
                "imaged_node_uuid": "test_uuid1",
                "image_now": True,
                "rdma_passthrough": False,
                "use_existing_network_settings": False
            },
            {
                "aos_version": "6.5.1",
                "cvm_ip": "test_gateway",
                "cvm_ram_gb": 12,
                "hypervisor_type": "kvm",
                "node_serial": "test2",
                "imaged_node_uuid": "test_uuid2",
                "image_now": True,
                "rdma_passthrough": False,
                "use_existing_network_settings": False
            }
        ]
    def test_create_fc_deployment_payload(self, imaged_cluster):
        cluster_info = {
            "use_existing_network_settings": False,
            "cluster_vip" : "test_vip",
            "rdma_passthrough": False,
            "cluster_name": "test_cluster",
            "cluster_size": 3,
            "dns_servers": ["test_dns"],
            "ntp_servers": ["test_ntp"],
            "imaging_parameters": {
                "hypervisor_type": "kvm",
                "aos_url": "http://test_url",
                "hypervisor_url": "http://test_url"
            },
            "re-image": True,
            "cvm_ram": 12,
            "cvm_vlan_id": None,
            "redundancy_factor" : 2,
            "timezone": "test_timezone"
        }
        existing_node_detail_dict = [
            {
                "aos_version": "6.5.1",
                "cvm_ip": "test_gateway",
                "ipmi_netmask": "test_netmask",
                "ipmi_gateway": "test_ipmi_netmask",
                "node_serial": "test1",
                "imaged_node_uuid": "test_uuid1",
             },
            {
                "aos_version": "6.5.1",
                "cvm_ip": "test_gateway",
                "ipmi_netmask": "test_netmask",
                "ipmi_gateway": "test_ipmi_netmask",
                "node_serial": "test2",
                "imaged_node_uuid": "test_uuid2",
             }
            ]
        updated_node_details_list = imaged_cluster.create_fc_deployment_payload(cluster_info, existing_node_detail_dict)
        assert updated_node_details_list == ({
                "aos_package_url": "http://test_url",
                "cluster_external_ip": "test_vip",
                "redundancy_factor": 2,
                "cluster_name": "test_cluster",
                "cluster_size": 3,
                "common_network_settings": {
                    "cvm_dns_servers": ["test_dns"],
                    "hypervisor_dns_servers": ["test_dns"],
                    "cvm_ntp_servers": ["test_ntp"],
                    "hypervisor_ntp_servers": ["test_ntp"],
                },
                "hypervisor_isos": [
                    {
                        "hypervisor_type": "kvm",
                        "url": "http://test_url",
                    },
                ],
                "timezone": "test_timezone",
                "nodes_list": [
                    {
                        "aos_version": "6.5.1",
                        "cvm_ip": "test_gateway",
                        "cvm_ram_gb": 12,
                        "ipmi_netmask": "test_netmask",
                        "ipmi_gateway": "test_ipmi_netmask",
                        "node_serial": "test1",
                        "imaged_node_uuid": "test_uuid1",
                        "rdma_passthrough": False,
                        "hypervisor_type": "kvm",
                        "image_now": True,
                        "cvm_ram_gb": 12,
                        "use_existing_network_settings": False
                    },
                    {
                        "aos_version": "6.5.1",
                        "cvm_ip": "test_gateway",
                        "cvm_ram_gb": 12,
                        "ipmi_netmask": "test_netmask",
                        "ipmi_gateway": "test_ipmi_netmask",
                        "node_serial": "test2",
                        "imaged_node_uuid": "test_uuid2",
                        "rdma_passthrough": False,
                        "hypervisor_type": "kvm",
                        "image_now": True,
                        "cvm_ram_gb": 12,
                        "use_existing_network_settings": False
                    }
                ]
            }, None)
        

