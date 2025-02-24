import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.eula import Eula
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestEula:
    @pytest.fixture
    def eula(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return Eula(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)

    def test_eula_init(self, eula):
        assert eula.resource_type == "/eulas"
        assert eula.session == self.session
        assert eula.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(eula, Eula)
        assert isinstance(eula, PeEntityV1)
    
    def test_is_eula_accepted(self, mocker, eula):
        # Test when EULA is accepted
        eula_response = [
            {
                "userDetailsList": [
                    {
                        "username": "test_user",
                        "companyName": "test_company",
                        "jobTitle": "test_job"
                    }
                ]
            }
        ]
        mock_read = mocker.patch.object(PeEntityV1, "read", return_value=eula_response)
        result = eula.is_eula_accepted()
        mock_read.assert_called_once()
        assert result == True

        # Test when EULA is not accepted
        mock_read.return_value = [{"some_key": "some", "other_key": "other"}]
        result = eula.is_eula_accepted()
        mock_read.assert_called()
        assert result == False

    def test_accept_eula(self, mocker, eula):
        # Test accepting EULA
        username = "test_user"
        company_name = "test_company"
        job_title = "test_job"
        payload_data = {
            "username" : username,
            "companyName" : company_name,
            "jobTitle" : job_title
        }
        mock_create = mocker.patch.object(PeEntityV1, "create")
        eula.accept_eula(username=username, company_name=company_name, job_title=job_title)
        mock_create.assert_called_once_with(data=payload_data, endpoint="accept")