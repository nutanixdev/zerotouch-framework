import pytest
import logging
from framework.scripts.python.helpers.fc.image_cluster_script import ImageClusterScript
from framework.scripts.python.helpers.fc.imaged_clusters import ImagedCluster
from framework.scripts.python.script import Script
from framework.helpers.rest_utils import RestAPIUtil
from unittest.mock import MagicMock

class TestImageClusterScript:
    @pytest.fixture
    def image_cluster_script(self, mocker):
        self.mock_pc_session = MagicMock(spec=RestAPIUtil)
        self.mock_cluster_data = {"cluster_name": "test_cluster"}
        self.mock_fc_deployment_logger = logging.getLogger("test")
        return ImageClusterScript(
            pc_session=self.mock_pc_session,
            cluster_data=self.mock_cluster_data,
            fc_deployment_logger=self.mock_fc_deployment_logger
        )
        
    def test_image_cluster_script_init(self, image_cluster_script):
        assert image_cluster_script.cluster_data == self.mock_cluster_data
        assert isinstance(image_cluster_script, ImageClusterScript)
        assert isinstance(image_cluster_script, Script)
        
    def test_execute(self, mocker, image_cluster_script):
        
        mock_imaging_get_spec = mocker.patch.object(
            image_cluster_script.imaging,"get_spec",
            return_value=({"spec": "test_spec"}, None)
        )
        mock_imaging_create = mocker.patch.object(
            image_cluster_script.imaging, "create",
            return_value={"imaged_cluster_uuid": "test_uuid"}
        )
        image_cluster_script.execute()
        mock_imaging_get_spec.assert_called_once_with(params=self.mock_cluster_data)
        mock_imaging_create.assert_called_once_with({"spec": "test_spec"})
        assert image_cluster_script.results == {"test_cluster": "test_uuid"}
        
        
        mock_imaging_get_spec.return_value = (None, "Error")
        image_cluster_script.execute()
        
        assert "Failed generating Image Nodes Spec: Error" in image_cluster_script.exceptions

        mock_imaging_get_spec.return_value = ({"spec": "test_spec"}, None)
        mock_imaging_create.side_effect = Exception("Error")
        image_cluster_script.execute()
        
        assert "Failed to deploy cluster test_cluster. Error: Error" in image_cluster_script.exceptions

    def test_verify(self):
        assert True
        #Verify method is not implemented in ImageClusterScript