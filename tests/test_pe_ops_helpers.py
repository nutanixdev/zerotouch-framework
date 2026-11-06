"""
Unit tests for PE-ops custom helpers: eula_pe, ad_server_pe, role_mapping_pe,
open_replication_ports, ha_reservation, and their manual entity-catalog and
custom_helpers registrations.
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Mock RestAPIUtil session."""
    session = MagicMock()
    session.get = MagicMock()
    session.post = MagicMock()
    session.put = MagicMock()
    session.delete = MagicMock()
    return session


# ===================================================================
# Registry / entity_map sanity checks
# ===================================================================


class TestPeOpsRegistry:
    EXPECTED_HELPERS = [
        "eula_pe",
        "ad_server_pe",
        "role_mapping_pe",
        "open_replication_ports",
        "ha_reservation",
    ]

    @pytest.mark.parametrize("name", EXPECTED_HELPERS)
    def test_registry_entry_exists(self, name):
        from ztf.custom_helpers import custom_helpers_registry

        assert name in custom_helpers_registry

    @pytest.mark.parametrize("name", EXPECTED_HELPERS)
    def test_entity_map_entry_exists(self, name):
        from ztf.entity_wrapper.entity_map import entity_map

        assert name in entity_map
        assert entity_map[name]["use_ztf_helper"] is True

    def test_registry_classes_importable(self):
        import importlib

        from ztf.custom_helpers import custom_helpers_registry

        for name in self.EXPECTED_HELPERS:
            entry = custom_helpers_registry[name]
            mod = importlib.import_module(entry["helper_module"])
            cls = getattr(mod, entry["helper_class"])
            assert cls is not None


# ===================================================================
# EulaPeHelper
# ===================================================================


class TestEulaPeHelper:
    def _make_helper(self, session, data=None):
        from ztf.helpers.eula_pe import EulaPeHelper

        return EulaPeHelper(session=session, data=data or {})

    def test_create_entity_accepts_eula(self, mock_session):
        mock_session.get.return_value = []
        mock_session.post.return_value = {}
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(
            {"username": "admin", "company_name": "Nutanix", "job_title": "Admin"}
        )
        assert ext_id == "eula_accepted"
        mock_session.post.assert_called_once()

    def test_create_entity_already_accepted_skips(self, mock_session):
        mock_session.get.return_value = [{"userDetailsList": [{"username": "admin"}]}]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(
            {"username": "admin", "company_name": "Nutanix", "job_title": "Admin"}
        )
        assert ext_id == "eula_accepted"
        mock_session.post.assert_not_called()

    def test_create_entity_missing_required_field(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="username"):
            helper.create_entity({"company_name": "Nutanix", "job_title": "Admin"})

    def test_create_entity_post_failure_raises(self, mock_session):
        mock_session.get.return_value = []
        mock_session.post.side_effect = Exception("network error")
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception, match="network error"):
            helper.create_entity(
                {"username": "admin", "company_name": "Nutanix", "job_title": "Admin"}
            )

    def test_is_eula_accepted_read_error_returns_false(self, mock_session):
        mock_session.get.side_effect = Exception("boom")
        helper = self._make_helper(mock_session)
        assert helper._is_eula_accepted() is False

    def test_update_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.update_entity("eula_accepted", {})

    def test_delete_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.delete_entity("eula_accepted")

    def test_list_entities_accepted(self, mock_session):
        mock_session.get.return_value = [{"userDetailsList": []}]
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert result == [{"extId": "eula_accepted", "status": "accepted"}]

    def test_list_entities_not_accepted(self, mock_session):
        mock_session.get.return_value = []
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_get_entity_by_ext_id_accepted(self, mock_session):
        """get_entity_by_ext_id always returns None: username/company_name/
        job_title can't be reconstructed from the read API, and there's
        nothing else meaningful to diff since update/delete aren't
        supported."""
        mock_session.get.return_value = [{"userDetailsList": []}]
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("eula_accepted")
        assert result is None

    def test_get_entity_by_ext_id_not_accepted(self, mock_session):
        mock_session.get.return_value = []
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("eula_accepted") is None


# ===================================================================
# AdServerPeHelper
# ===================================================================


class TestAdServerPeHelper:
    def _make_helper(self, session, data=None):
        from ztf.helpers.ad_server_pe import AdServerPeHelper

        return AdServerPeHelper(session=session, data=data or {})

    def _valid_entity_data(self, **overrides):
        data = {
            "ad_name": "corp-ad",
            "ad_domain": "corp.nutanix.com",
            "ad_directory_url": "ldap://10.0.0.1:389",
            "directory_type": "ACTIVE_DIRECTORY",
            "service_account_username": "svc",
            "service_account_password": "pass",
        }
        data.update(overrides)
        return data

    def test_create_entity_success(self, mock_session):
        mock_session.get.return_value = []
        mock_session.post.return_value = {}
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(self._valid_entity_data())
        assert ext_id == "corp-ad"
        mock_session.post.assert_called_once()

    def test_create_entity_already_exists_skips(self, mock_session):
        mock_session.get.return_value = [{"name": "corp-ad"}]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(self._valid_entity_data())
        assert ext_id == "corp-ad"
        mock_session.post.assert_not_called()

    def test_create_entity_missing_required_field(self, mock_session):
        helper = self._make_helper(mock_session)
        data = self._valid_entity_data()
        del data["ad_domain"]
        with pytest.raises(ValueError, match="ad_domain"):
            helper.create_entity(data)

    def test_create_entity_defaults_applied(self, mock_session):
        mock_session.get.return_value = []
        mock_session.post.return_value = {}
        helper = self._make_helper(mock_session)
        helper.create_entity(self._valid_entity_data())
        payload = mock_session.post.call_args[1]["data"]
        assert payload["groupSearchType"] == "NON_RECURSIVE"
        assert payload["connectionType"] == "LDAP"

    def test_create_entity_post_failure_raises(self, mock_session):
        mock_session.get.return_value = []
        mock_session.post.side_effect = Exception("network error")
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception, match="network error"):
            helper.create_entity(self._valid_entity_data())

    def test_update_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.update_entity("corp-ad", {})

    def test_delete_entity_success(self, mock_session):
        mock_session.delete.return_value = {}
        helper = self._make_helper(mock_session)
        assert helper.delete_entity("corp-ad") is True

    def test_delete_entity_failure_raises(self, mock_session):
        mock_session.delete.side_effect = Exception("boom")
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception, match="boom"):
            helper.delete_entity("corp-ad")

    def test_list_entities(self, mock_session):
        mock_session.get.return_value = [{"name": "corp-ad"}, {"name": "other-ad"}]
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert len(result) == 2

    def test_list_entities_with_filter(self, mock_session):
        mock_session.get.return_value = [{"name": "corp-ad"}, {"name": "other-ad"}]
        helper = self._make_helper(mock_session)
        result = helper.list_entities(custom_filter={"ad_name": "corp-ad"})
        assert len(result) == 1
        assert result[0]["ad_name"] == "corp-ad"

    def test_list_entities_normalizes_to_snake_case_schema(self, mock_session):
        """list_entities/get_entity_by_ext_id must return the same
        snake_case keys create_entity accepts, so state bodies stay
        comparable to user config for drift detection."""
        mock_session.get.return_value = [
            {
                "name": "corp-ad",
                "domain": "corp.nutanix.com",
                "directoryUrl": "ldap://10.0.0.1:389",
                "directoryType": "ACTIVE_DIRECTORY",
                "connectionType": "LDAP",
                "groupSearchType": "NON_RECURSIVE",
                "serviceAccountUsername": "svc",
            }
        ]
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert result[0] == {
            "extId": "corp-ad",
            "ad_name": "corp-ad",
            "ad_domain": "corp.nutanix.com",
            "ad_directory_url": "ldap://10.0.0.1:389",
            "directory_type": "ACTIVE_DIRECTORY",
            "connection_type": "LDAP",
            "group_search_type": "NON_RECURSIVE",
            "service_account_username": "svc",
        }

    def test_get_entity_by_ext_id_strips_ext_id_from_body(self, mock_session):
        mock_session.get.return_value = [{"name": "corp-ad", "domain": "d.local"}]
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("corp-ad")
        assert "extId" not in result
        assert result["ad_name"] == "corp-ad"

    def test_list_entities_non_list_response(self, mock_session):
        mock_session.get.return_value = {}
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_list_entities_error_returns_empty(self, mock_session):
        mock_session.get.side_effect = Exception("down")
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_get_entity_by_ext_id_found(self, mock_session):
        mock_session.get.return_value = [{"name": "corp-ad"}]
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("corp-ad") is not None

    def test_get_entity_by_ext_id_not_found(self, mock_session):
        mock_session.get.return_value = []
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("nonexistent") is None


# ===================================================================
# RoleMappingPeHelper
# ===================================================================


class TestRoleMappingPeHelper:
    def _make_helper(self, session, data=None):
        from ztf.helpers.role_mapping_pe import RoleMappingPeHelper

        return RoleMappingPeHelper(session=session, data=data or {})

    def _valid_entity_data(self, **overrides):
        data = {
            "directory_name": "corp-ad",
            "role_type": "ROLE_CLUSTER_ADMIN",
            "entity_type": "GROUP",
            "values": ["Domain Admins"],
        }
        data.update(overrides)
        return data

    def test_create_entity_success(self, mock_session):
        mock_session.get.return_value = []
        mock_session.post.return_value = {}
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(self._valid_entity_data())
        assert ext_id == "corp-ad:ROLE_CLUSTER_ADMIN:GROUP"
        mock_session.post.assert_called_once()

    def test_create_entity_already_exists_skips(self, mock_session):
        mock_session.get.return_value = [
            {"role": "ROLE_CLUSTER_ADMIN", "entityType": "GROUP"}
        ]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(self._valid_entity_data())
        assert ext_id == "corp-ad:ROLE_CLUSTER_ADMIN:GROUP"
        mock_session.post.assert_not_called()

    def test_create_entity_missing_required_field(self, mock_session):
        helper = self._make_helper(mock_session)
        data = self._valid_entity_data()
        del data["values"]
        with pytest.raises(ValueError, match="values"):
            helper.create_entity(data)

    def test_create_entity_post_failure_raises(self, mock_session):
        mock_session.get.return_value = []
        mock_session.post.side_effect = Exception("network error")
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception, match="network error"):
            helper.create_entity(self._valid_entity_data())

    def test_update_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.update_entity("corp-ad:ROLE_CLUSTER_ADMIN:GROUP", {})

    def test_delete_entity_success(self, mock_session):
        mock_session.delete.return_value = {}
        helper = self._make_helper(mock_session)
        assert helper.delete_entity("corp-ad:ROLE_CLUSTER_ADMIN:GROUP") is True

    def test_delete_entity_invalid_ext_id_raises(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="directory_name:role_type:entity_type"):
            helper.delete_entity("bad-ext-id")

    def test_delete_entity_failure_raises(self, mock_session):
        mock_session.delete.side_effect = Exception("boom")
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception, match="boom"):
            helper.delete_entity("corp-ad:ROLE_CLUSTER_ADMIN:GROUP")

    def test_list_entities_missing_filter_returns_empty(self, mock_session):
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_list_entities_success(self, mock_session):
        mock_session.get.return_value = [
            {"role": "ROLE_CLUSTER_ADMIN", "entityType": "GROUP"}
        ]
        helper = self._make_helper(mock_session)
        result = helper.list_entities(custom_filter={"directory_name": "corp-ad"})
        assert len(result) == 1
        assert result[0]["extId"] == "corp-ad:ROLE_CLUSTER_ADMIN:GROUP"

    def test_list_entities_non_list_response(self, mock_session):
        mock_session.get.return_value = {}
        helper = self._make_helper(mock_session)
        result = helper.list_entities(custom_filter={"directory_name": "corp-ad"})
        assert result == []

    def test_list_entities_error_returns_empty(self, mock_session):
        mock_session.get.side_effect = Exception("down")
        helper = self._make_helper(mock_session)
        result = helper.list_entities(custom_filter={"directory_name": "corp-ad"})
        assert result == []

    def test_get_entity_by_ext_id_invalid_format(self, mock_session):
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("bad-ext-id") is None

    def test_get_entity_by_ext_id_found(self, mock_session):
        mock_session.get.return_value = [
            {
                "role": "ROLE_CLUSTER_ADMIN",
                "entityType": "GROUP",
                "entityValues": ["Domain Admins"],
            }
        ]
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("corp-ad:ROLE_CLUSTER_ADMIN:GROUP")
        assert result is not None
        assert "extId" not in result
        assert result == {
            "directory_name": "corp-ad",
            "role_type": "ROLE_CLUSTER_ADMIN",
            "entity_type": "GROUP",
            "values": ["Domain Admins"],
        }

    def test_get_entity_by_ext_id_not_found(self, mock_session):
        mock_session.get.return_value = []
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("corp-ad:ROLE_CLUSTER_ADMIN:GROUP")
        assert result is None


# ===================================================================
# OpenReplicationPortsHelper
# ===================================================================


class TestOpenReplicationPortsHelper:
    def _make_helper(self, session, data=None):
        from ztf.helpers.open_replication_ports import OpenReplicationPortsHelper

        return OpenReplicationPortsHelper(session=session, data=data or {})

    @patch("ztf.helpers.open_replication_ports.SSHCvm")
    def test_create_entity_success(self, MockSSHCvm, mock_session):
        mock_ssh = MagicMock()
        mock_ssh.enable_replication_ports.return_value = (True, "opened")
        MockSSHCvm.return_value = mock_ssh

        helper = self._make_helper(
            mock_session,
            data={"credentials": {"cvm_creds": {"username": "u", "password": "p"}}},
        )
        ext_id = helper.create_entity(
            {"cluster_ip": "10.0.0.1", "cvm_credential": "cvm_creds"}
        )
        assert ext_id == "10.0.0.1"
        mock_ssh.enable_replication_ports.assert_called_once_with(
            ports=[2020, 2030, 2036, 2073, 2090]
        )
        mock_ssh.close.assert_called_once()

    def test_create_entity_missing_cluster_ip(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="cluster_ip"):
            helper.create_entity({"cvm_credential": "creds"})

    def test_create_entity_missing_credential(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="cvm_credential"):
            helper.create_entity({"cluster_ip": "10.0.0.1"})

    @patch("ztf.helpers.open_replication_ports.SSHCvm")
    def test_create_entity_inline_credential_dict(self, MockSSHCvm, mock_session):
        mock_ssh = MagicMock()
        mock_ssh.enable_replication_ports.return_value = (True, "opened")
        MockSSHCvm.return_value = mock_ssh

        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(
            {
                "cluster_ip": "10.0.0.1",
                "cvm_credential": {"username": "admin", "password": "secret"},
            }
        )
        assert ext_id == "10.0.0.1"
        MockSSHCvm.assert_called_once_with(
            cvm_ip="10.0.0.1", username="admin", password="secret"
        )

    def test_create_entity_unresolvable_credential_raises(self, mock_session):
        helper = self._make_helper(mock_session, data={"credentials": {}})
        with pytest.raises(ValueError, match="Cannot resolve credential"):
            helper.create_entity(
                {"cluster_ip": "10.0.0.1", "cvm_credential": "nonexistent"}
            )

    def test_create_entity_empty_username_password_raises(self, mock_session):
        helper = self._make_helper(
            mock_session,
            data={"credentials": {"creds": {"username": "", "password": ""}}},
        )
        with pytest.raises(ValueError, match="username or password"):
            helper.create_entity({"cluster_ip": "10.0.0.1", "cvm_credential": "creds"})

    def test_create_entity_rejects_injection_ports(self, mock_session):
        helper = self._make_helper(
            mock_session,
            data={"credentials": {"cvm_creds": {"username": "u", "password": "p"}}},
        )
        with pytest.raises(ValueError, match="Invalid replication port"):
            helper.create_entity(
                {
                    "cluster_ip": "10.0.0.1",
                    "cvm_credential": "cvm_creds",
                    "ports": ["2020; rm -rf /"],
                }
            )

    @patch("ztf.helpers.open_replication_ports.SSHCvm")
    def test_create_entity_ssh_failure_raises(self, MockSSHCvm, mock_session):
        mock_ssh = MagicMock()
        mock_ssh.enable_replication_ports.return_value = (False, "SSH timeout")
        MockSSHCvm.return_value = mock_ssh

        helper = self._make_helper(
            mock_session,
            data={"credentials": {"creds": {"username": "u", "password": "p"}}},
        )
        with pytest.raises(Exception, match="Failed to open replication ports"):
            helper.create_entity({"cluster_ip": "10.0.0.1", "cvm_credential": "creds"})
        mock_ssh.close.assert_called_once()

    @patch("ztf.helpers.open_replication_ports.SSHCvm")
    def test_update_entity_delegates_to_create(self, MockSSHCvm, mock_session):
        mock_ssh = MagicMock()
        mock_ssh.enable_replication_ports.return_value = (True, "opened")
        MockSSHCvm.return_value = mock_ssh

        helper = self._make_helper(
            mock_session,
            data={"credentials": {"creds": {"username": "u", "password": "p"}}},
        )
        ext_id = helper.update_entity("10.0.0.1", {"cvm_credential": "creds"})
        assert ext_id == "10.0.0.1"

    def test_delete_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.delete_entity("10.0.0.1")

    def test_list_entities_returns_empty(self, mock_session):
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_get_entity_by_ext_id_returns_none(self, mock_session):
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("10.0.0.1") is None


# ===================================================================
# HaReservationHelper
# ===================================================================


class TestHaReservationHelper:
    def _make_helper(self, session, data=None):
        from ztf.helpers.ha_reservation import HaReservationHelper

        return HaReservationHelper(session=session, data=data or {})

    def test_create_entity_updates_ha(self, mock_session):
        mock_session.get.side_effect = [
            {"numNodes": 3},
            {"numHostFailuresToTolerate": 0},
        ]
        mock_session.put.return_value = {"taskUuid": "task-1"}

        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity({"num_host_failure_to_tolerate": 1})
        assert ext_id == "ha_reservation"
        mock_session.put.assert_called_once_with(
            "api/nutanix/v0.8/ha", data={"numHostFailuresToTolerate": 1}
        )

    def test_create_entity_single_node_skips(self, mock_session):
        mock_session.get.return_value = {"numNodes": 1}

        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity({})
        assert ext_id == "ha_reservation"
        mock_session.put.assert_not_called()

    def test_create_entity_already_set_skips(self, mock_session):
        mock_session.get.side_effect = [
            {"numNodes": 3},
            {"numHostFailuresToTolerate": 1},
        ]

        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity({"num_host_failure_to_tolerate": 1})
        assert ext_id == "ha_reservation"
        mock_session.put.assert_not_called()

    def test_create_entity_get_num_nodes_failure_defaults_zero(self, mock_session):
        mock_session.get.side_effect = [Exception("timeout"), {}]
        mock_session.put.return_value = {}

        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity({})
        assert ext_id == "ha_reservation"
        mock_session.put.assert_called_once()

    def test_create_entity_failure_raises(self, mock_session):
        mock_session.get.side_effect = Exception("connection refused")
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception, match="connection refused"):
            helper.create_entity({})

    def test_update_entity_delegates_to_create(self, mock_session):
        mock_session.get.side_effect = [{"numNodes": 3}, {}]
        mock_session.put.return_value = {}

        helper = self._make_helper(mock_session)
        ext_id = helper.update_entity("ha_reservation", {})
        assert ext_id == "ha_reservation"

    def test_delete_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.delete_entity("ha_reservation")

    def test_list_entities_success(self, mock_session):
        mock_session.get.return_value = {"numHostFailuresToTolerate": 1}

        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert len(result) == 1
        assert result[0]["extId"] == "ha_reservation"
        assert result[0]["num_host_failure_to_tolerate"] == 1

    def test_list_entities_error_returns_empty(self, mock_session):
        mock_session.get.side_effect = Exception("down")
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert result == []

    def test_get_entity_by_ext_id_success(self, mock_session):
        mock_session.get.return_value = {"numHostFailuresToTolerate": 1}

        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("ha_reservation")
        assert "extId" not in result
        assert result["num_host_failure_to_tolerate"] == 1

    def test_get_entity_by_ext_id_error_returns_none(self, mock_session):
        mock_session.get.side_effect = Exception("down")
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("ha_reservation") is None


# ===================================================================
# SSHCvm.enable_replication_ports
# ===================================================================


class TestSSHCvmEnableReplicationPorts:
    def _make_ssh(self):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        return SSHCvm("10.0.0.1", "user", "pass")

    def test_allssh_success(self):
        ssh = self._make_ssh()
        with patch.object(
            ssh, "_execute_command", return_value=(True, "ok")
        ) as mock_exec:
            success, output = ssh.enable_replication_ports()
            assert success is True
            assert output == "ok"
            assert "allssh" in mock_exec.call_args[0][0]

    def test_allssh_unavailable_falls_back_to_direct(self):
        ssh = self._make_ssh()
        with patch.object(
            ssh,
            "_execute_command",
            side_effect=[(False, "bash: allssh: command not found"), (True, "ok")],
        ) as mock_exec:
            success, output = ssh.enable_replication_ports(ports=[2020])
            assert success is True
            assert mock_exec.call_count == 2

    def test_direct_fallback_also_fails(self):
        ssh = self._make_ssh()
        with patch.object(
            ssh,
            "_execute_command",
            side_effect=[
                (False, "bash: allssh: command not found"),
                (False, "permission denied"),
            ],
        ):
            success, output = ssh.enable_replication_ports()
            assert success is False
            assert output == "permission denied"

    def test_other_failure_returns_false(self):
        ssh = self._make_ssh()
        with patch.object(
            ssh, "_execute_command", return_value=(False, "connection reset")
        ):
            success, output = ssh.enable_replication_ports()
            assert success is False
            assert output == "connection reset"

    def test_rejects_non_integer_ports(self):
        ssh = self._make_ssh()
        with pytest.raises(ValueError, match="Invalid replication port"):
            ssh.enable_replication_ports(ports=["2020; rm -rf /"])

    def test_rejects_out_of_range_ports(self):
        ssh = self._make_ssh()
        with pytest.raises(ValueError, match="1-65535"):
            ssh.enable_replication_ports(ports=[0])
        with pytest.raises(ValueError, match="1-65535"):
            ssh.enable_replication_ports(ports=[65536])

    def test_rejects_bool_and_empty_ports(self):
        ssh = self._make_ssh()
        with pytest.raises(ValueError, match="list of integers"):
            ssh.enable_replication_ports(ports=True)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="non-empty list"):
            ssh.enable_replication_ports(ports=[])

    def test_accepts_numeric_strings_and_interpolates_only_ints(self):
        ssh = self._make_ssh()
        with patch.object(
            ssh, "_execute_command", return_value=(True, "ok")
        ) as mock_exec:
            success, _ = ssh.enable_replication_ports(ports=["2020", 2030])
        assert success is True
        cmd = mock_exec.call_args[0][0]
        assert "-p 2020,2030 -a" in cmd
        assert ";" not in cmd
