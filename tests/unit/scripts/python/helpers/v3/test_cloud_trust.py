import pytest
from unittest.mock import MagicMock
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.cloud_trust import CloudTrust

class TestCloudTrust:
    @pytest.fixture 
    def cloud_trust(self): 
        self.session = MagicMock(spec=RestAPIUtil) 
        return CloudTrust(session=self.session)
    
    def test_cloud_trust_init(self, cloud_trust): 
        ''' Test that the CloudTrust class is an instance of PcEntity and that the resource_type attribute is set correctly '''
        assert cloud_trust.resource_type == "/cloud_trusts"
        assert cloud_trust.session == self.session
        assert isinstance(cloud_trust, CloudTrust)
        assert isinstance(cloud_trust, PcEntity)
    
    def test_get_payload(self):
        cloud_type = "AWS"
        remote_pc = "https://remote-pc.example.com"
        remote_pc_username = "admin"
        remote_pc_password = "password"
        expected_payload = { "spec": { "name": "", "description": "", "resources": { "cloud_type": cloud_type, "password": remote_pc_password, "url": remote_pc, "username": remote_pc_username } } }
        payload = CloudTrust.get_payload(cloud_type, remote_pc, remote_pc_username, remote_pc_password)
        assert payload == expected_payload
