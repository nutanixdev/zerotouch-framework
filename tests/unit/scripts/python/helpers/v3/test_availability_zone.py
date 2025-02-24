import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.availabilty_zone import AvailabilityZone

class TestAvailabilityZone:

    @pytest.fixture
    def availability_zone(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return AvailabilityZone(session=self.session)

    def test_availability_zone_init(self, availability_zone):
        '''
        Test that the AvailabilityZone class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert availability_zone.resource_type == "/availability_zones"
        assert availability_zone.session == self.session
        assert isinstance(availability_zone, AvailabilityZone)
        assert isinstance(availability_zone, PcEntity)

    def test_get_mgmt_url_by_name(self, availability_zone, mocker):
        entity_name = "test_az"
        expected_mgmt_url = "http://management.url"
        mock_entity = {
            "status": {
                "resources": {
                    "management_url": expected_mgmt_url
                }
            }
        }
       
        mock_get_entity_by_name = mocker.patch.object(PcEntity, 'get_entity_by_name', return_value=mock_entity)

        mgmt_url = availability_zone.get_mgmt_url_by_name(entity_name=entity_name)

        mock_get_entity_by_name.assert_called_once_with(entity_name, filter="name==test_az")
        assert mgmt_url == expected_mgmt_url

    def test_get_mgmt_url_by_name_not_found(self, availability_zone, mocker):
        entity_name = "test_az"
        mock_get_entity_by_name = mocker.patch.object(PcEntity, 'get_entity_by_name', return_value=None)

        with pytest.raises(Exception) as excinfo:
            availability_zone.get_mgmt_url_by_name(entity_name=entity_name)
       
        assert str(excinfo.value) == f"AZ with name {entity_name} doesn't exist!"

    def test_get_mgmt_url_by_name_no_mgmt_url(self, availability_zone, mocker):
        entity_name = "test_az"
        mock_entity = {
            "status": {
                "resources": {
                    "management_url": ""  # Explicitly set to an empty string to trigger the exception
                }
            }
        }
       
        mock_get_entity_by_name = mocker.patch.object(PcEntity, 'get_entity_by_name', return_value=mock_entity)

        with pytest.raises(Exception) as excinfo:
            availability_zone.get_mgmt_url_by_name(entity_name=entity_name)
       
        assert str(excinfo.value) == "Couldn't fetch mgmt url"