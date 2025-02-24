import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.v3.syslog import RemoteSyslog, RemoteSyslogModule
from framework.scripts.python.helpers.pc_entity import PcEntity

@pytest.fixture
def remote_syslog(mocker):
    session = mocker.MagicMock()
    return RemoteSyslog(session)


@pytest.fixture
def remote_syslog_module(mocker):
    session = mocker.MagicMock()
    return RemoteSyslogModule(session)


class TestRemoteSyslog:
    def test_remote_syslog_init(self, remote_syslog):
        assert remote_syslog.resource_type == "/remote_syslog_servers"
        assert remote_syslog.kind == "remote_syslog_server"
        assert remote_syslog.session is not None

    def test_get_payload(self, remote_syslog):
        payload = remote_syslog.get_payload(
            server_name="test_server",
            ip_address="192.168.1.1",
            port=514,
            network_protocol="TCP",
            module_list=["ACROPOLIS", "GENESIS"],
            spec_version="1.0"
        )

        expected_payload = {
            "spec": {
                "resources": {
                    "server_name": "test_server",
                    "ip_address": "192.168.1.1",
                    "port": 514,
                    "network_protocol": "TCP",
                    "module_list": ["ACROPOLIS", "GENESIS"]
                }
            },
            "metadata": {
                "kind": "remote_syslog_server",
                "spec_version": "1.0"
            },
            "api_version": "3.1.0"
        }

        assert payload == expected_payload

    def test_create_syslog_server(self, remote_syslog, mocker):
        mock_create = mocker.patch.object(PcEntity, 'create', return_value={"status": "success"})

        response = remote_syslog.create_syslog_server(
            server_name="test_server",
            ip_address="192.168.1.1",
            port=514,
            network_protocol="TCP",
            module_list=["ACROPOLIS", "GENESIS"]
        )

        assert response == {"status": "success"}
        payload = remote_syslog.get_payload(
            server_name="test_server",
            ip_address="192.168.1.1",
            port=514,
            network_protocol="TCP",
            module_list=["ACROPOLIS", "GENESIS"]
        )
        mock_create.assert_called_once_with(data=payload)

    def test_update_syslog_server(self, remote_syslog, mocker):
        mock_update = mocker.patch.object(PcEntity, 'update', return_value={"status": "success"})

        response = remote_syslog.update_syslog_server(
            server_name="test_server",
            ip_address="192.168.1.1",
            port=514,
            network_protocol="TCP",
            module_list=["ACROPOLIS", "GENESIS"],
            uuid="12345",
            spec_version="1.0"
        )

        assert response == {"status": "success"}
        payload = remote_syslog.get_payload(
            server_name="test_server",
            ip_address="192.168.1.1",
            port=514,
            network_protocol="TCP",
            module_list=["ACROPOLIS", "GENESIS"],
            spec_version="1.0"
        )
        mock_update.assert_called_once_with(data=payload, endpoint="12345")


class TestRemoteSyslogModule:
    def test_remote_syslog_module_init(self, remote_syslog_module):
        assert remote_syslog_module.resource_type == "/remote_syslog_modules"
        assert remote_syslog_module.kind == "remote_syslog_module"
        assert remote_syslog_module.session is not None

    def test_create(self, remote_syslog_module, mocker):
        mock_create = mocker.patch.object(PcEntity, 'create', return_value={"status": "success"})

        response = remote_syslog_module.create(
            log_level=0,
            modules=["ACROPOLIS", "GENESIS"]
        )

        assert response == {"status": "success"}
        payload = {
            "spec": {
                "resources": {
                    "module_list": [
                        {"module_name": "ACROPOLIS", "log_severity_level": 0},
                        {"module_name": "GENESIS", "log_severity_level": 0}
                    ]
                }
            },
            "metadata": {
                "kind": "remote_syslog_module"
            },
            "api_version": "3.1.0"
        }
        mock_create.assert_called_once_with(data=payload)