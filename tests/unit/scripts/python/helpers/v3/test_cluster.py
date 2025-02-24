'''import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from framework.scripts.python.helpers.v1.cluster import Cluster
from unittest.mock import MagicMock

class TestCluster:
    @pytest.fixture
    def cluster(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Cluster(session=self.session)
    
    def test_cluster_init(self, cluster):
        assert cluster.resource_type == "/cluster"
        assert cluster.session == self.session
        assert isinstance(cluster, Cluster)
        assert isinstance(cluster, PeEntityV1)

    def test_add_name_servers(self, cluster, mocker):
        name_server_list = ["ns1.example.com", "ns2.example.com"]
        mock_create = mocker.patch.object(PeEntityV1, "create")
        cluster.add_name_servers(name_server_list)
        mock_create.assert_called_once_with(
            data=name_server_list, endpoint="name_servers/add_list"
            )
        
    def test_delete_name_servers(self, cluster, mocker):
        name_server_list = ["ns1.example.com", "ns2.example.com"]
        mock_create = mocker.patch.object(PeEntityV1, "create")
        cluster.delete_name_servers(name_server_list)
        mock_create.assert_called_once_with(
            data=name_server_list, endpoint="name_servers/remove_list"
            )

    def test_get_name_servers(self, cluster, mocker):
        mock_read = mocker.patch.object(PeEntityV1, "read")
        cluster.get_name_servers()
        mock_read.assert_called_once_with(endpoint="name_servers")
        
    def test_add_ntp_servers(self, cluster, mocker):
        ntp_server_list = ["ntp1.example.com", "ntp2.example.com"]
        mock_create = mocker.patch.object(PeEntityV1, "create")
        cluster.add_ntp_servers(ntp_server_list)
        mock_create.assert_called_once_with(
            data=ntp_server_list, endpoint="ntp_servers/add_list"
            )

    def test_delete_ntp_servers(self, cluster, mocker):
        ntp_server_list = ["ntp1.example.com", "ntp2.example.com"]
        mock_create = mocker.patch.object(PeEntityV1, "create")
        cluster.delete_ntp_servers(ntp_server_list)
        mock_create.assert_called_once_with(
            data=ntp_server_list, endpoint="ntp_servers/remove_list"
            )

    def test_get_ntp_servers(self, cluster, mocker):
        mock_read = mocker.patch.object(PeEntityV1, "read")
        cluster.get_ntp_servers()
        mock_read.assert_called_once_with(endpoint="ntp_servers")

    def test_update_rebuild_reservation(self, cluster, mocker):
        enable = True
        mock_update = mocker.patch.object(PeEntityV1, "update")
        cluster.update_rebuild_reservation(enable)
        mock_update.assert_called_once_with(
            data={"enableRebuildReservation": enable}, method="PATCH"
            )

    def test_get_smptp_config(self, cluster, mocker):
        mock_read = mocker.patch.object(PeEntityV1, "read")
        cluster.get_smptp_config()
        mock_read.assert_called_once_with(endpoint="smtp")

    def test_update_smptp_config(self, cluster, mocker):
        address = "smtp.example.com"
        port = 587
        fromEmailAddress = "noreply@example.com"
        mock_update = mocker.patch.object(PeEntityV1, "update")
        cluster.update_smptp_config(address, port, fromEmailAddress)
        mock_update.assert_called_once_with(
            data={
                "address": address,
                "port": port,
                "fromEmailAddress": fromEmailAddress,
                "secureMode": "NONE"
            }, endpoint="smtp"
            )
        '''

import pytest
from unittest.mock import MagicMock
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.cluster import Cluster


class TestCluster:

    @pytest.fixture
    def cluster(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Cluster(session=self.session)

    def test_cluster_init(self, cluster):
        '''
        Test that the Cluster class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert cluster.resource_type == "/clusters"
        assert cluster.session == self.session
        assert isinstance(cluster, Cluster)
        assert isinstance(cluster, PcEntity)
        assert cluster.uuid_ip_map == {}
        assert cluster.uuid_name_map == {}
        assert cluster.name_uuid_map == {}
        assert cluster.ip_uuid_map == {}

    def test_get_pe_info_list(self, cluster, mocker):
        mock_clusters = [
            {
                "status": {
                    "resources": {
                        "config": {
                            "service_list": ["SERVICE"]
                        },
                        "network": {
                            "external_ip": "192.168.1.1"
                        }
                    },
                    "name": "Cluster1"
                },
                "spec": {},
                "metadata": {
                    "uuid": "uuid1"
                }
            },
            {
                "status": {
                    "resources": {
                        "config": {
                            "service_list": ["SERVICE"]
                        },
                        "network": {
                            "external_ip": "192.168.1.2"
                        }
                    },
                    "name": "Cluster2"
                },
                "spec": {},
                "metadata": {
                    "uuid": "uuid2"
                }
            },
            {
                "status": {
                    "resources": {
                        "config": {
                            "service_list": ["PRISM_CENTRAL"]
                        }
                    }
                }
            }
        ]

        mock_list = mocker.patch.object(PcEntity, 'list', return_value=mock_clusters)

        cluster.get_pe_info_list()

        expected_name_uuid_map = {
            "Cluster1": "uuid1",
            "Cluster2": "uuid2"
        }
        expected_uuid_name_map = {
            "uuid1": "Cluster1",
            "uuid2": "Cluster2"
        }
        expected_uuid_ip_map = {
            "uuid1": "192.168.1.1",
            "uuid2": "192.168.1.2"
        }
        expected_ip_uuid_map = {
            "192.168.1.1": "uuid1",
            "192.168.1.2": "uuid2"
        }

        assert cluster.name_uuid_map == expected_name_uuid_map
        assert cluster.uuid_name_map == expected_uuid_name_map
        assert cluster.uuid_ip_map == expected_uuid_ip_map
        assert cluster.ip_uuid_map == expected_ip_uuid_map
        mock_list.assert_called_once()

    def test_get_pe_info_list_no_external_ip(self, cluster, mocker):
        mock_clusters = [
            {
                "status": {
                    "resources": {
                        "config": {
                            "service_list": ["SERVICE"]
                        },
                        "network": {}
                    },
                    "name": "Cluster1"
                },
                "spec": {},
                "metadata": {
                    "uuid": "uuid1"
                }
            }
        ]

        mock_list = mocker.patch.object(PcEntity, 'list', return_value=mock_clusters)

        cluster.get_pe_info_list()

        expected_name_uuid_map = {
            "Cluster1": "uuid1"
        }
        expected_uuid_name_map = {
            "uuid1": "Cluster1"
        }
        expected_uuid_ip_map = {
            "uuid1": None
        }
        expected_ip_uuid_map = {
            None: "uuid1"
        }

        assert cluster.name_uuid_map == expected_name_uuid_map
        assert cluster.uuid_name_map == expected_uuid_name_map
        assert cluster.uuid_ip_map == expected_uuid_ip_map
        assert cluster.ip_uuid_map == expected_ip_uuid_map
        mock_list.assert_called_once()

    def test_get_pe_info_list_no_name(self, cluster, mocker):
        mock_clusters = [
            {
                "status": {
                    "resources": {
                        "config": {
                            "service_list": ["SERVICE"]
                        },
                        "network": {
                            "external_ip": "192.168.1.1"
                        }
                    }
                },
                "spec": {},
                "metadata": {
                    "uuid": "uuid1"
                }
            }
        ]

        mock_list = mocker.patch.object(PcEntity, 'list', return_value=mock_clusters)

        cluster.get_pe_info_list()

        assert cluster.name_uuid_map == {}
        assert cluster.uuid_name_map == {}
        assert cluster.uuid_ip_map == {}
        assert cluster.ip_uuid_map == {}
        mock_list.assert_called_once()

    def test_get_pe_info_list_no_uuid(self, cluster, mocker):
        mock_clusters = [
            {
                "status": {
                    "resources": {
                        "config": {
                            "service_list": ["SERVICE"]
                        },
                        "network": {
                            "external_ip": "192.168.1.1"
                        }
                    },
                    "name": "Cluster1"
                },
                "spec": {}
            }
        ]

        mock_list = mocker.patch.object(PcEntity, 'list', return_value=mock_clusters)

        cluster.get_pe_info_list()

        expected_name_uuid_map = {
            "Cluster1": None
        }
        expected_uuid_name_map = {
            None: "Cluster1"
        }
        expected_uuid_ip_map = {
            None: "192.168.1.1"
        }
        expected_ip_uuid_map = {
            "192.168.1.1": None
        }

        assert cluster.name_uuid_map == expected_name_uuid_map
        assert cluster.uuid_name_map == expected_uuid_name_map
        assert cluster.uuid_ip_map == expected_uuid_ip_map
        assert cluster.ip_uuid_map == expected_ip_uuid_map
        mock_list.assert_called_once()