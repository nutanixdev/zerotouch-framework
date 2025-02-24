import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.v3.service import Service


@pytest.fixture
def service(mocker):
    session = mocker.MagicMock()
    return Service(session)


class TestService:
    def test_service_init(self, service):
        assert service.resource_type == "/services"
        assert service.kind == "service"
        assert service.session is not None

    def test_get_microseg_status(self, service):
        service.read = MagicMock(return_value={"service_enablement_status": "ENABLED"})

        status = service.get_microseg_status()

        print(f"Returned Status: {status}")
        print(f"Service read call count: {service.read.call_count}")
        print(f"Service read call args: {service.read.call_args}")

        assert status == "ENABLED"

    def test_get_dr_status(self, service):
        service.read = MagicMock(return_value={"service_enablement_status": "DISABLED"})

        status = service.get_dr_status()

        assert status == "DISABLED"

    def test_enable_microseg(self, service):
        service.create = MagicMock(return_value={"task_uuid": "test-uuid"})

        response = service.enable_microseg()

        print(f"Service create call args: {service.create.call_args}")

        assert response == {"task_uuid": "test-uuid"}
        service.create.assert_called_once_with(data={'state': 'ENABLE'}, endpoint='microseg')

    def test_disable_microseg(self, service):
        service.create = MagicMock(return_value={"task_uuid": "test-uuid"})

        response = service.disable_microseg()

        assert response == {"task_uuid": "test-uuid"}
        service.create.assert_called_once_with(data={'state': 'DISABLE'}, endpoint='microseg')

    def test_enable_leap(self, service):
        service.create = MagicMock(return_value={"task_uuid": "test-uuid"})

        response = service.enable_leap()

        assert response == {"task_uuid": "test-uuid"}
        service.create.assert_called_once_with(data={'state': 'ENABLE'}, endpoint='disaster_recovery')

    def test_get_oss_status(self, service):
        service.read = MagicMock(return_value={"service_enablement_status": "ENABLED"})

        status = service.get_oss_status()

        assert status == "ENABLED"

    def test_enable_oss(self, service):
        service.create = MagicMock(return_value={"task_uuid": "test-uuid"})

        response = service.enable_oss()

        assert response == {"task_uuid": "test-uuid"}
        service.create.assert_called_once_with(data={'state': 'ENABLE'}, endpoint='oss')
