import pytest
import json
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.genesis import Genesis
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestGenesis:
    @pytest.fixture
    def genesis(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return Genesis(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)
    
    def test_genesis_init(self, genesis):
        assert genesis.resource_type == "/genesis"
        assert genesis.session == self.session
        assert genesis.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(genesis, Genesis)
        assert isinstance(genesis, PeEntityV1)
    
    def test_is_karbon_enabled(self, mocker, genesis):
        # Test when Karbon is enabled
        karbon_response = {"value": '{".return": true}'}
        
        mock_read = mocker.patch.object(PeEntityV1, "read", return_value=karbon_response)
        result = genesis.is_karbon_enabled()
        mock_read.assert_called_once()
        assert result == True

        # Test when Karbon is not enabled
        mock_read.return_value = [{"some_key": "some", "other_key": "other"}]
        with pytest.raises(Exception) as E:
            result = genesis.is_karbon_enabled()
            mock_read.assert_called()
            assert E.message == "Cannot fetch Karbon status"
        

    def test_is_fc_enabled(self, mocker, genesis):
        # Test when FC is enabled
        fc_response = {"value": '{".return": true}'}
        
        mock_read = mocker.patch.object(PeEntityV1, "read", return_value=fc_response)
        result = genesis.is_fc_enabled()
        mock_read.assert_called_once()
        assert result == True

        # Test when FC is not enabled
        mock_read.return_value = [{"some_key": "some", "other_key": "other"}]
        with pytest.raises(Exception) as E:
            result = genesis.is_fc_enabled()
            mock_read.assert_called()
            assert E.message == "Cannot fetch Foundation Central status"

    def test_enable_karbon(self, mocker, genesis):
        json_data = {".oid": "ClusterManager",
                     ".method": "enable_service_with_prechecks",
                     ".kwargs": {
                         "service_list_json":
                             json.dumps({
                                 "service_list": [
                                     "KarbonUIService",
                                     "KarbonCoreService"
                                 ]
                             })
                     }}

        payload = {"value": json.dumps(json_data)}
        mock_read = mocker.patch.object(
            PeEntityV1, "read", return_value={"value": '{".return": true}'})
        result = genesis.enable_karbon()
        mock_read.assert_called_once_with(data=payload, method="POST")
        assert result == True

    def test_enable_fc(self, mocker, genesis):
        json_data = {".oid": "ClusterManager",
                     ".method": "enable_service",
                     ".kwargs": {
                         "service_list_json":
                             json.dumps({
                                 "service_list": [
                                     "FoundationCentralService"
                                 ]
                             })
                     }}
        payload = {"value": json.dumps(json_data)}
        mock_read = mocker.patch.object(
            PeEntityV1, "read", return_value={"value": '{".return": true}'})
        result = genesis.enable_fc()
        mock_read.assert_called_once_with(data=payload, method="POST")
        assert result == True

    def test_list(self, genesis):
        with pytest.raises(Exception) as E:
            genesis.list()
            assert E.message == "Not implemented"

    def test_update(self, genesis):
        with pytest.raises(Exception) as E:
            genesis.update()
            assert E.message == "Not implemented"