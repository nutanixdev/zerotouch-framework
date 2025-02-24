import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v2.cluster import Cluster
from framework.scripts.python.helpers.pe_entity_v2 import PeEntityV2
from unittest.mock import MagicMock

class TestCluster:

    @pytest.fixture
    def cluster(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Cluster(session=self.session)
    
    @pytest.fixture
    def mock_read(self, mocker):
        return mocker.patch.object(PeEntityV2, "read", return_value={
            "cluster_external_data_services_ipaddress": "1.1.1.1"
        })
    
    @pytest.fixture
    def mock_update(self, mocker):
        return mocker.patch.object(PeEntityV2, "update", return_value={'status': 200})
    
    def test_cluster_init(self, cluster):
        assert cluster.resource_type == "/cluster"
        assert cluster.cluster_info == {}
        assert isinstance(cluster, Cluster)
        assert isinstance(cluster, PeEntityV2)

    def test_get_cluster_info(self, cluster, mock_read):
        cluster.get_cluster_info()
        mock_read.assert_called_once()
        assert (
            "cluster_external_data_services_ipaddress" in cluster.cluster_info and
            cluster.cluster_info["cluster_external_data_services_ipaddress"] == "1.1.1.1"
            )

    def test_update_dsip(self, cluster, mock_read, mock_update):
        dsip = "192.168.1.100"
        result = cluster.update_dsip(dsip)
        mock_update.assert_called_once_with(data={
            "cluster_external_data_services_ipaddress": dsip
        })
        assert result == {'status': 200}