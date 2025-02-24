import pytest
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
        