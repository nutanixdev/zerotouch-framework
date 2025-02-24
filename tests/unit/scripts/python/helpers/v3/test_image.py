import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.cluster import Cluster as PcCluster
from framework.scripts.python.helpers.v3.image import Image

class TestImage:

    @pytest.fixture
    def image(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Image(session=self.session)

    def test_image_init(self, image):
        '''
        Test that the Image class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert image.resource_type == "/images"
        assert image.session == self.session
        assert isinstance(image, Image)
        assert isinstance(image, PcEntity)

    @patch('framework.scripts.python.helpers.v3.image.PcCluster')
    def test_url_upload(self, MockPcCluster, image, mocker):
        mock_cluster_instance = MockPcCluster.return_value
        mock_cluster_instance.get_pe_info_list.return_value = None
        mock_cluster_instance.name_uuid_map = {
            "cluster-name1": "uuid1",
            "cluster-name2": "uuid2"
        }

        image_config_list = [
            {
                'name': 'image_name',
                'description': 'test image',
                'image_type': 'DISK_IMAGE',
                'url': 'http://where-the-file-is-present',
                'cluster_name_list': ['cluster-name1', 'cluster-name2']
            }
        ]

        expected_payload_list = [
            {
                "spec": {
                    "name": "image_name",
                    "description": "test image",
                    "resources": {
                        "image_type": "DISK_IMAGE",
                        "source_uri": "http://where-the-file-is-present",
                        "initial_placement_ref_list": [
                            {'kind': 'cluster', 'uuid': 'uuid1'},
                            {'kind': 'cluster', 'uuid': 'uuid2'}
                        ]
                    }
                },
                "metadata": {
                    "kind": "image"
                }
            }
        ]

        mock_batch_create = mocker.patch.object(image.batch_op, 'batch_create', return_value=[{"status": "success"}])

        response = image.url_upload(image_config_list)

        mock_batch_create.assert_called_once_with(request_payload_list=expected_payload_list)
        assert response == [{"status": "success"}]

    @patch('framework.scripts.python.helpers.v3.image.PcCluster')
    def test_url_upload_empty_cluster_list(self, MockPcCluster, image, mocker):
        mock_cluster_instance = MockPcCluster.return_value
        mock_cluster_instance.get_pe_info_list.return_value = None
        mock_cluster_instance.name_uuid_map = {}

        image_config_list = [
            {
                'name': 'image_name',
                'description': 'test image',
                'image_type': 'DISK_IMAGE',
                'url': 'http://where-the-file-is-present',
                'cluster_name_list': []
            }
        ]

        expected_payload_list = [
            {
                "spec": {
                    "name": "image_name",
                    "description": "test image",
                    "resources": {
                        "image_type": "DISK_IMAGE",
                        "source_uri": "http://where-the-file-is-present",
                        "initial_placement_ref_list": []
                    }
                },
                "metadata": {
                    "kind": "image"
                }
            }
        ]

        mock_batch_create = mocker.patch.object(image.batch_op, 'batch_create', return_value=[{"status": "success"}])

        response = image.url_upload(image_config_list)

        mock_batch_create.assert_called_once_with(request_payload_list=expected_payload_list)
        assert response == [{"status": "success"}]

    @patch('framework.scripts.python.helpers.v3.image.PcCluster')
    def test_url_upload_partial_cluster_list(self, MockPcCluster, image, mocker):
        mock_cluster_instance = MockPcCluster.return_value
        mock_cluster_instance.get_pe_info_list.return_value = None
        mock_cluster_instance.name_uuid_map = {
            "cluster-name1": "uuid1"
        }

        image_config_list = [
            {
                'name': 'image_name',
                'description': 'test image',
                'image_type': 'DISK_IMAGE',
                'url': 'http://where-the-file-is-present',
                'cluster_name_list': ['cluster-name1', 'cluster-name2']
            }
        ]

        expected_payload_list = [
            {
                "spec": {
                    "name": "image_name",
                    "description": "test image",
                    "resources": {
                        "image_type": "DISK_IMAGE",
                        "source_uri": "http://where-the-file-is-present",
                        "initial_placement_ref_list": [
                            {'kind': 'cluster', 'uuid': 'uuid1'},
                            {'kind': 'cluster', 'uuid': None}
                        ]
                    }
                },
                "metadata": {
                    "kind": "image"
                }
            }
        ]

        mock_batch_create = mocker.patch.object(image.batch_op, 'batch_create', return_value=[{"status": "success"}])

        response = image.url_upload(image_config_list)

        mock_batch_create.assert_called_once_with(request_payload_list=expected_payload_list)
        assert response == [{"status": "success"}]

    @patch('framework.scripts.python.helpers.v3.image.PcCluster')
    def test_url_upload_multiple_images(self, MockPcCluster, image, mocker):
        mock_cluster_instance = MockPcCluster.return_value
        mock_cluster_instance.get_pe_info_list.return_value = None
        mock_cluster_instance.name_uuid_map = {
            "cluster-name1": "uuid1",
            "cluster-name2": "uuid2"
        }

        image_config_list = [
            {
                'name': 'image_name1',
                'description': 'test image 1',
                'image_type': 'DISK_IMAGE',
                'url': 'http://where-the-file-is-present1',
                'cluster_name_list': ['cluster-name1']
            },
            {
                'name': 'image_name2',
                'description': 'test image 2',
                'image_type': 'ISO_IMAGE',
                'url': 'http://where-the-file-is-present2',
                'cluster_name_list': ['cluster-name2']
            }
        ]

        expected_payload_list = [
            {
                "spec": {
                    "name": "image_name1",
                    "description": "test image 1",
                    "resources": {
                        "image_type": "DISK_IMAGE",
                        "source_uri": "http://where-the-file-is-present1",
                        "initial_placement_ref_list": [
                            {'kind': 'cluster', 'uuid': 'uuid1'}
                        ]
                    }
                },
                "metadata": {
                    "kind": "image"
                }
            },
            {
                "spec": {
                    "name": "image_name2",
                    "description": "test image 2",
                    "resources": {
                        "image_type": "ISO_IMAGE",
                        "source_uri": "http://where-the-file-is-present2",
                        "initial_placement_ref_list": [
                            {'kind': 'cluster', 'uuid': 'uuid2'}
                        ]
                    }
                },
                "metadata": {
                    "kind": "image"
                }
            }
        ]

        mock_batch_create = mocker.patch.object(image.batch_op, 'batch_create', return_value=[{"status": "success"}])

        response = image.url_upload(image_config_list)

        mock_batch_create.assert_called_once_with(request_payload_list=expected_payload_list)
        assert response == [{"status": "success"}]
