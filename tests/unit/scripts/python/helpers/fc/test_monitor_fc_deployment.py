import pytest
import time
from framework.scripts.python.helpers.fc.monitor_fc_deployment import MonitorDeployment
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.script import Script
from framework.scripts.python.helpers.fc.imaged_clusters import ImagedCluster
from framework.scripts.python.helpers.v2.cluster import Cluster as PeCluster
from unittest.mock import MagicMock, patch

class TestMonitorFcDeployment:
    @pytest.fixture
    def monitor_deployment(self):
        return MonitorDeployment(
            pc_session=MagicMock(spec=RestAPIUtil), cluster_name="test_cluster",
            imaged_cluster_uuid="test_uuid", fc_deployment_logger=MagicMock()
            )
    
    def test_monitor_deployment_init(self, monitor_deployment):
        assert monitor_deployment.cluster_name == "test_cluster"
        assert monitor_deployment.imaged_cluster_uuid == "test_uuid"
        assert isinstance(monitor_deployment.imaging, ImagedCluster)
        assert isinstance(monitor_deployment, Script)
        assert isinstance(monitor_deployment, MonitorDeployment)
    
    def test_execute(self, monitor_deployment, mocker):
        mock_read = mocker.patch.object(ImagedCluster, 'read')
        mock_read.return_value = {
            "cluster_status": {
                "imaging_stopped": True,
                "aggregate_percent_complete": 100
                }
            }
        mock_status = mocker.patch.object(monitor_deployment, '_get_deployment_status', return_value="test_status")
        monitor_deployment.execute()
        mock_status.assert_called()
        assert monitor_deployment.results == {"test_cluster": {"result": "COMPLETED", "status": "test_status", "imaged_cluster_uuid": "test_uuid"}}
        mock_read.return_value["cluster_status"]["aggregate_percent_complete"] = 75
        monitor_deployment.execute()
        mock_status.assert_called()
        assert monitor_deployment.results == {"test_cluster": {"result": "FAILED", "status": "test_status", "imaged_cluster_uuid": "test_uuid"}}
        mock_time = mocker.patch('time.time', return_value=time.time())
        mock_time.side_effect = [0,3 * 60 * 60+1]
        mock_read.return_value["cluster_status"]["imaging_stopped"] = False
        monitor_deployment.execute()
        mock_status.assert_called()
        assert monitor_deployment.results == {"test_cluster": {"result": "PENDING", "status": "test_status", "imaged_cluster_uuid": "test_uuid"}}
        
    def test_verify(self, monitor_deployment, mocker):
        monitor_deployment.results = {"test_cluster": {"result": "test_result"}}
        mock_read = mocker.patch.object(ImagedCluster, 'read')
        mock_read.return_value = {
            "cluster_status": {
                "imaging_stopped": True,
                "aggregate_percent_complete": 100
                },
            "cluster_external_ip": "test_ip"
            }
        mock_check_cluster_vip_access = mocker.patch.object(monitor_deployment, 'check_cluster_vip_access')
        mock_check_cluster_vip_access.return_value=True
        monitor_deployment.verify()
        assert monitor_deployment.results["test_cluster"]["cluster_vip"] == "test_ip"
        assert monitor_deployment.results["test_cluster"]["cluster_vip_access"] == "PASS"
        
        mock_check_cluster_vip_access.return_value = False
        monitor_deployment.verify()
        assert monitor_deployment.results["test_cluster"]["cluster_vip_access"] == "Failed to access Cluster VIP test_ip"
        
        mock_read.return_value["cluster_status"]["aggregate_percent_complete"] = 75
        monitor_deployment.verify()
        assert monitor_deployment.results["test_cluster"]["cluster_vip_access"] == "Deployment Failed"
        
        mock_read.return_value["cluster_status"]["imaging_stopped"] = False
        monitor_deployment.verify()
        assert monitor_deployment.results["test_cluster"]["cluster_vip_access"] == "Deployment In-Progress"
        
        mock_read.return_value["cluster_external_ip"] = ""
        monitor_deployment.verify()
        assert monitor_deployment.results["test_cluster"]["cluster_vip_access"] == "Not Applicable"
        
    def test_check_cluster_vip_access(self, monitor_deployment, mocker):
        mock_pe_cluster_read = mocker.patch.object(PeCluster, "read")
        mock_exception = Exception()
        mock_exception.message = "401 Client Error: UNAUTHORIZED"
        mock_pe_cluster_read.side_effect = mock_exception
                
        assert monitor_deployment.check_cluster_vip_access("test_ip") == True
        
        mock_exception.message = "Some other error"
        mock_pe_cluster_read.side_effect = mock_exception
        #mock_session.read.side_effect = Exception("Some other error")
        assert monitor_deployment.check_cluster_vip_access("test_ip") == False

    def test_get_deployment_status(self, monitor_deployment):
            progress = {
                "cluster_status": {
                    "cluster_progress_details": {
                        "cluster_name": "test_cluster",
                        "status": "test_status",
                        "message_list": ["test_message"]
                    },
                    "node_progress_details": [
                        {
                            "imaged_node_uuid": "test_node_uuid_1",
                            "status": "test_status_1",
                            "message_list": ["test_message_1"]
                        },
                        {
                            "imaged_node_uuid": "test_node_uuid_2",
                            "status": "test_status_2",
                            "message_list": ["test_message_2"]
                        }
                    ]
                }
            }
            cluster_progress = "\n\tcluster_name: test_cluster\n" \
                              "\tstatus: test_status\n" \
                              "\tmessage: test_message\n"
            node_progress = "\tstatus: test_status_1\n\tmessage: test_message_1\n" \
                            "\tstatus: test_status_2\n\tmessage: test_message_2\n"
            expected_output = "{0}\nClusters: {1}\nNodes: {2}".format("",cluster_progress,node_progress)

            output = monitor_deployment._get_deployment_status(progress)
            assert output == expected_output
            
    def test_get_cluster_progress_messages(self, monitor_deployment):
            response = {
                "cluster_status": {
                    "cluster_progress_details": {
                        "cluster_name": "test_cluster",
                        "status": "test_status",
                        "message_list": ["test_message"]
                    }
                }
            }
            expected_output = "\n\tcluster_name: test_cluster\n" \
                              "\tstatus: test_status\n" \
                              "\tmessage: test_message\n"
            output = monitor_deployment._get_cluster_progress_messages(response, "cluster_progress_details", "cluster_name")
            assert output == expected_output

    def test_get_node_progress_messages(self, monitor_deployment):
            response = {
                "cluster_status": {
                    "node_progress_details": [
                        {"imaged_node_uuid": "test_node_uuid_1", "status": "test_status_1", "message_list": ["test_message_1"]},
                        {"imaged_node_uuid": "test_node_uuid_2", "status": "test_status_2", "message_list": ["test_message_2"]}
                    ]
                }
            }
            expected_output = "\tstatus: test_status_1\n\tmessage: test_message_1\n" \
                              "\tstatus: test_status_2\n\tmessage: test_message_2\n"
            output = monitor_deployment._get_node_progress_messages(response, "node_progress_details", "imaged_node_uuid")
            assert output == expected_output
    

        