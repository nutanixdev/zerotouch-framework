import pytest
from framework.scripts.python.helpers.fc.enable_one_node import EnableOneNode
from framework.scripts.python.script import Script

class TestEnableOneNode:
    @pytest.fixture
    def enable_one_node(self, mocker):
        self.cvm_ip = "test_ip"
        self.cvm_username = "test_username"
        self.cvm_password = "test_password"
        self.mock_ssh_cvm = mocker.patch(
            "framework.scripts.python.helpers.fc.enable_one_node.SSHCVM")
        return EnableOneNode(
            cvm_ip=self.cvm_ip, cvm_username=self.cvm_username, cvm_password=self.cvm_password
        )
    
    def test_enable_one_node_init(self, enable_one_node):
        assert enable_one_node.cvm_ip == self.cvm_ip
        assert enable_one_node.ssh_cvm == self.mock_ssh_cvm.return_value
        assert isinstance(enable_one_node, EnableOneNode)
        assert isinstance(enable_one_node, Script)
    
    def test_execute(self, mocker, enable_one_node):
        self.mock_ssh_cvm.return_value.enable_one_node.return_value = (True, None)
        
        enable_one_node.execute()
        self.mock_ssh_cvm.return_value.enable_one_node.assert_called_once()
        assert enable_one_node.results == {
            "cvm_ip": self.cvm_ip, "status": True, "error": None
            }
        
        self.mock_ssh_cvm.return_value.enable_one_node.return_value = (False, "Error")
        enable_one_node.execute()
        self.mock_ssh_cvm.return_value.enable_one_node.assert_called()
        assert enable_one_node.results == {
            "cvm_ip": self.cvm_ip, "status": False, "error": "Error"
            }
    
    def test_verify(self, enable_one_node):
        enable_one_node.verify()
        assert True
