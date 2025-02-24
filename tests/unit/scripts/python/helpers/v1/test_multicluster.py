import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.multicluster import MultiCluster
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestMultiCluster:
    @pytest.fixture
    def multi_cluster(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return MultiCluster(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)
    
    def test_multi_cluster_init(self, multi_cluster):
        assert multi_cluster.resource_type == "/multicluster"
        assert multi_cluster.session == self.session
        assert multi_cluster.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(multi_cluster, MultiCluster)
        assert isinstance(multi_cluster, PeEntityV1)
    
    def test_get_cluster_external_state(self, mocker, multi_cluster):
        mock_read = mocker.patch.object(PeEntityV1, "read", return_value={
            "value": '{"cluster_external_state": "kSucceeded"}'})
        result = multi_cluster.get_cluster_external_state()
        mock_read.assert_called_once_with(endpoint="cluster_external_state")
        assert result == {"value": '{"cluster_external_state": "kSucceeded"}'}
        
    def test_register_pe_to_pc(self, mocker, multi_cluster):
        pc_ip = "1.1.1.1"
        pc_username = "admin"
        pc_password = "password"
        data = {
          "ipAddresses": [pc_ip],
          "username": pc_username,
          "password": pc_password
        }
        mock_create = mocker.patch.object(
            PeEntityV1, "create", return_value={"value": '{"status": "kSucceeded"}'})
        result = multi_cluster.register_pe_to_pc(pc_ip, pc_username, pc_password)
        mock_create.assert_called_once_with(data=data, endpoint="add_to_multicluster")
        assert result == {"value": '{"status": "kSucceeded"}'}
    
    def test_deregister_pe_from_pc(self, mocker, multi_cluster):
        pc_ip = "1.1.1.1"
        pc_username = "admin"
        pc_password = "password"
        data = {
          "ipAddresses": [pc_ip],
          "username": pc_username,
          "password": pc_password
        }
        mock_create = mocker.patch.object(
            PeEntityV1, "create", return_value={"value": '{"status": "kSucceeded"}'})
        result = multi_cluster.deregister_pe_from_pc(pc_ip, pc_username, pc_password)
        mock_create.assert_called_once_with(data=data, endpoint="remove_from_multicluster")
        assert result == {"value": '{"status": "kSucceeded"}'}                          