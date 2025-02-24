import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.ova import Ova
from framework.scripts.python.helpers.v3.cluster import Cluster as PcCluster

class TestOva:

    @pytest.fixture
    def ova(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Ova(session=self.session)

    def test_ova_init(self, ova):
        '''
        Test that the Ova class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert ova.resource_type == "/ovas"
        assert ova.session == self.session
        assert isinstance(ova, Ova)
        assert isinstance(ova, PcEntity)

    @patch('framework.scripts.python.helpers.v3.ova.PcCluster')
    def test_url_upload(self, MockPcCluster, ova, mocker):
        mock_cluster_instance = MockPcCluster.return_value
        mock_cluster_instance.get_pe_info_list.return_value = None
        mock_cluster_instance.name_uuid_map = {
            "cluster1": "uuid1",
            "cluster2": "uuid2"
        }

        ova_config_list = [
            {
                'url': 'http://where-the-file-is-present',
                'name': 'ova-name',
                'cluster_name_list': ['cluster1', 'cluster2']
            }
        ]

        expected_payload_list = [
            {
                "url": "http://where-the-file-is-present",
                "name": "ova-name",
                "upload_cluster_ref_list": [
                    {'kind': 'cluster', 'uuid': 'uuid1'},
                    {'kind': 'cluster', 'uuid': 'uuid2'}
                ]
            }
        ]

        mock_batch_create = mocker.patch.object(ova.batch_op, 'batch_create', return_value=[{"task_uuid": "task1"}])

        response = ova.url_upload(ova_config_list)

        mock_batch_create.assert_called_once_with(request_payload_list=expected_payload_list)
        assert response == [{"task_uuid": "task1"}]

    def test_get_vm_spec_from_ova_uuid(self, ova, mocker):
        ova_uuid = "test_uuid"
        mock_response = {
            "vm_spec": {
                "spec": {"vm_name": "test_vm"}
            }
        }

        mock_read = mocker.patch.object(ova, 'read', return_value=mock_response)

        vm_spec = ova.get_vm_spec_from_ova_uuid(ova_uuid)

        mock_read.assert_called_once_with(uuid=ova_uuid, endpoint="vm_spec")
        assert vm_spec == {"vm_name": "test_vm"}

    @patch('framework.scripts.python.helpers.v3.ova.PcCluster')
    def test_get_ova_by_cluster_reference(self, MockPcCluster, ova, mocker):
        mock_cluster_instance = MockPcCluster.return_value
        mock_cluster_instance.get_pe_info_list.return_value = None
        mock_cluster_instance.name_uuid_map = {
            "cluster1": "uuid1"
        }

        ova_name = "test_ova"
        cluster_name = "cluster1"
        mock_entities = [
            {
                "info": {
                    "current_cluster_reference_list": [
                        {"uuid": "uuid1"}
                    ]
                }
            }
        ]

        mock_list = mocker.patch.object(ova, 'list', return_value=mock_entities)

        ova_entity = ova.get_ova_by_cluster_reference(ova_name, cluster_name=cluster_name)

        mock_list.assert_called_once_with(filter=f"name=={ova_name}")
        assert ova_entity == mock_entities[0]

    @patch('framework.scripts.python.helpers.v3.ova.PcCluster')
    def test_get_ova_by_cluster_reference_no_cluster_uuid(self, MockPcCluster, ova, mocker):
        mock_cluster_instance = MockPcCluster.return_value
        mock_cluster_instance.get_pe_info_list.return_value = None
        mock_cluster_instance.name_uuid_map = {
            "cluster1": "uuid1"
        }

        ova_name = "test_ova"
        cluster_name = "cluster1"
        mock_entities = [
            {
                "info": {
                    "current_cluster_reference_list": [
                        {"uuid": "uuid1"}
                    ]
                }
            }
        ]

        mock_list = mocker.patch.object(ova, 'list', return_value=mock_entities)

        ova_entity = ova.get_ova_by_cluster_reference(ova_name, cluster_name=cluster_name)

        mock_list.assert_called_once_with(filter=f"name=={ova_name}")
        assert ova_entity == mock_entities[0]

    def test_get_ova_by_cluster_reference_not_found(self, ova, mocker):
        ova_name = "test_ova"
        cluster_name = "cluster1"
        mock_entities = [
            {
                "info": {
                    "current_cluster_reference_list": [
                        {"uuid": "uuid2"}
                    ]
                }
            }
        ]

        mock_list = mocker.patch.object(ova, 'list', return_value=mock_entities)

        ova_entity = ova.get_ova_by_cluster_reference(ova_name, cluster_name=cluster_name, cluster_uuid="uuid1")

        mock_list.assert_called_once_with(filter=f"name=={ova_name}")
        assert ova_entity is None