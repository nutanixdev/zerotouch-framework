"""
Unit tests for FC helpers: fc_cluster, fc_imaging,
generate_fc_api_key, enable_foundation_central, update_cvm_foundation,
and custom_helpers registry.
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
# FcCreateClusterHelper
# ===================================================================


class TestFcClusterHelper:
    def _make_helper(self, session):
        from ztf.helpers.fc_cluster import FcClusterHelper

        return FcClusterHelper(session=session)

    # --- create_entity ---

    def test_create_entity_success(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1", "cvm_ip": "10.0.0.1"},
                    {"node_serial": "SN2", "cvm_ip": "10.0.0.2"},
                ]
            },
            {"imaged_cluster_uuid": "uuid-abc-123"},
        ]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(
            {
                "cluster_name": "test-cluster",
                "nodes_list": [{"node_serial": "SN1"}, {"node_serial": "SN2"}],
            }
        )
        assert ext_id == "uuid-abc-123"
        assert mock_session.post.call_count == 2

    def test_create_entity_missing_cluster_name(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="cluster_name"):
            helper.create_entity({"nodes_list": [{"node_serial": "SN1"}]})

    def test_create_entity_missing_nodes(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="nodes_list"):
            helper.create_entity({"cluster_name": "c1"})

    def test_create_entity_missing_serials_in_fc(self, mock_session):
        mock_session.post.return_value = {
            "imaged_nodes": [
                {"node_serial": "SN1", "cvm_ip": "10.0.0.1"},
            ]
        }
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="Not enough imaged nodes"):
            helper.create_entity(
                {
                    "cluster_name": "c1",
                    "nodes_list": [
                        {"node_serial": "SN1"},
                        {"node_serial": "SN_MISSING"},
                    ],
                }
            )

    def test_create_entity_sets_default_node_role(self, mock_session):
        """Node role is fetched from FC API, not set by default anymore."""
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1", "node_role": "hyperconverged"},
                    {"node_serial": "SN2", "node_role": "storage"},
                ]
            },
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes_list": [{"node_serial": "SN1"}, {"node_serial": "SN2"}],
            }
        )
        create_call_payload = mock_session.post.call_args_list[1]
        nodes = create_call_payload[1]["data"]["nodes_list"]
        # Roles come from FC API response
        assert nodes[0]["node_role"] == "hyperconverged"
        assert nodes[1]["node_role"] == "storage"

    def test_create_entity_respects_custom_role(self, mock_session):
        """Custom role override from user is not supported - roles come from FC API."""
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1", "node_role": "hyperconverged"}]},
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes_list": [{"node_serial": "SN1"}],  # Don't specify node_role
            }
        )
        create_call_payload = mock_session.post.call_args_list[1]
        nodes = create_call_payload[1]["data"]["nodes_list"]
        # Role comes from FC API, not from user
        assert nodes[0]["node_role"] == "hyperconverged"

    def test_create_entity_skip_cluster_creation_always_false(self, mock_session):
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1"}]},
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes_list": [{"node_serial": "SN1"}],
            }
        )
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["skip_cluster_creation"] is False

    def test_create_entity_optional_fields(self, mock_session):
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1", "node_role": "hyperconverged"}]},
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes_list": [{"node_serial": "SN1"}],
                "cluster_external_ip": "10.0.0.99",
                "network_settings": {"dns": "8.8.8.8"},  # New name
                "redundancy_factor": 3,
                "timezone": "America/Los_Angeles",  # New parameter
            }
        )
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["cluster_external_ip"] == "10.0.0.99"
        assert payload["common_network_settings"] == {
            "dns": "8.8.8.8"
        }  # Maps to FC API name
        assert payload["redundancy_factor"] == 3
        assert payload["timezone"] == "America/Los_Angeles"

    def test_create_entity_common_network_settings_backward_compat(self, mock_session):
        """Old common_network_settings name still works for backward compatibility."""
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1", "node_role": "hyperconverged"}]},
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes_list": [{"node_serial": "SN1"}],
                "common_network_settings": {"dns": "8.8.8.8"},  # Old name
            }
        )
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["common_network_settings"] == {"dns": "8.8.8.8"}

    def test_create_entity_empty_response_raises(self, mock_session):
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1"}]},
            None,
        ]
        helper = self._make_helper(mock_session)
        with pytest.raises(RuntimeError, match="Empty response"):
            helper.create_entity(
                {
                    "cluster_name": "c1",
                    "nodes_list": [{"node_serial": "SN1"}],
                }
            )

    # --- update / delete ---

    def test_update_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.update_entity("id1", {})

    def test_delete_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.delete_entity("id1")

    # --- list_entities ---

    def test_list_entities(self, mock_session):
        mock_session.post.return_value = {
            "imaged_clusters": [
                {"cluster_name": "c1", "imaged_cluster_uuid": "u1"},
                {"cluster_name": "c2", "imaged_cluster_uuid": "u2"},
            ]
        }
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert len(result) == 2
        assert result[0]["cluster_name"] == "c1"

    def test_list_entities_with_filter(self, mock_session):
        mock_session.post.return_value = {
            "imaged_clusters": [
                {"cluster_name": "c1", "imaged_cluster_uuid": "u1"},
                {"cluster_name": "c2", "imaged_cluster_uuid": "u2"},
            ]
        }
        helper = self._make_helper(mock_session)
        result = helper.list_entities(custom_filter={"cluster_name": "c2"})
        assert len(result) == 1
        assert result[0]["cluster_name"] == "c2"

    def test_list_entities_api_failure_returns_empty(self, mock_session):
        mock_session.post.side_effect = Exception("API down")
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert result == []

    # --- get_entity_by_ext_id ---

    def test_get_entity_by_ext_id_found(self, mock_session):
        mock_session.post.return_value = {
            "imaged_clusters": [
                {"cluster_name": "c1", "imaged_cluster_uuid": "u1"},
            ]
        }
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("u1")
        assert result is not None
        assert result["extId"] == "u1"

    def test_get_entity_by_ext_id_not_found(self, mock_session):
        mock_session.post.return_value = {"imaged_clusters": []}
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("nonexistent") is None

    def test_get_entity_by_ext_id_by_name(self, mock_session):
        mock_session.post.return_value = {
            "imaged_clusters": [
                {"cluster_name": "my-cluster", "imaged_cluster_uuid": "u1"},
            ]
        }
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("my-cluster")
        assert result is not None


# ===================================================================
# FcImagingHelper
# ===================================================================


class TestFcImagingHelper:
    def _make_helper(self, session):
        from ztf.helpers.fc_imaging import FcImagingHelper

        return FcImagingHelper(session=session)

    # --- create_entity ---

    def test_imaging_only_success(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1", "cvm_ip": "10.0.0.1"},
                    {"node_serial": "SN2", "cvm_ip": "10.0.0.2"},
                ]
            },
            {"imaged_cluster_uuid": "uuid-img-1"},
        ]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(
            {
                "cluster_name": "img-deploy",
                "nodes_list": [{"node_serial": "SN1"}, {"node_serial": "SN2"}],
                "imaging_parameters": {"aos_package_url": "http://example.com/aos.tar"},
                "hypervisor_isos": [{"url": "http://example.com/hyp.iso"}],
            }
        )
        assert ext_id == "uuid-img-1"
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["skip_cluster_creation"] is True

    def test_imaging_only_requires_2_nodes(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="at least 2 nodes"):
            helper.create_entity(
                {
                    "cluster_name": "img-deploy",
                    "nodes_list": [{"node_serial": "SN1"}],
                    "skip_cluster_creation": True,
                }
            )

    def test_image_and_cluster_single_node_ok(self, mock_session):
        """Image + cluster mode allows single node (no 2-node minimum)."""
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1"}]},
            {"imaged_cluster_uuid": "uuid-ic-1"},
        ]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity(
            {
                "cluster_name": "img-cluster",
                "nodes_list": [{"node_serial": "SN1"}],
                "skip_cluster_creation": False,
                "imaging_parameters": {"aos_package_url": "http://example.com/aos.tar"},
            }
        )
        assert ext_id == "uuid-ic-1"
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["skip_cluster_creation"] is False
        assert "cluster_size" in payload

    def test_image_now_set_on_resolved_nodes(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1", "cvm_ip": "10.0.0.1"},
                    {"node_serial": "SN2", "cvm_ip": "10.0.0.2"},
                ]
            },
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "deploy",
                "nodes_list": [{"node_serial": "SN1"}, {"node_serial": "SN2"}],
            }
        )
        payload = mock_session.post.call_args_list[1][1]["data"]
        for node in payload["nodes_list"]:
            assert node["image_now"] is True

    def test_per_node_overrides_merged(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1", "cvm_ip": "10.0.0.1"},
                    {"node_serial": "SN2", "cvm_ip": "10.0.0.2"},
                ]
            },
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "deploy",
                "nodes_list": [
                    {"node_serial": "SN1", "cvm_ip": "10.1.1.1"},
                    {"node_serial": "SN2"},
                ],
            }
        )
        payload = mock_session.post.call_args_list[1][1]["data"]
        sn1 = [n for n in payload["nodes_list"] if n["node_serial"] == "SN1"][0]
        assert sn1["cvm_ip"] == "10.1.1.1"

    def test_missing_serials_raises(self, mock_session):
        mock_session.post.return_value = {
            "imaged_nodes": [
                {"node_serial": "SN1"},
            ]
        }
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="not available in FC"):
            helper.create_entity(
                {
                    "cluster_name": "deploy",
                    "nodes_list": [
                        {"node_serial": "SN1"},
                        {"node_serial": "SN_MISSING"},
                    ],
                    "skip_cluster_creation": False,
                }
            )

    def test_imaging_parameters_in_payload(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ]
            },
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "deploy",
                "nodes_list": [{"node_serial": "SN1"}, {"node_serial": "SN2"}],
                "imaging_parameters": {
                    "aos_package_url": "http://pkg/aos.tar",
                    "aos_package_sha256sum": "abc123",
                },
                "hypervisor_isos": [{"url": "http://iso/hyp.iso"}],
            }
        )
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["aos_package_url"] == "http://pkg/aos.tar"
        assert payload["aos_package_sha256sum"] == "abc123"
        assert payload["hypervisor_isos"] == [{"url": "http://iso/hyp.iso"}]

    def test_cluster_fields_only_when_not_skipping(self, mock_session):
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1"}, {"node_serial": "SN2"}]},
            {"imaged_cluster_uuid": "uuid-1"},
        ]
        helper = self._make_helper(mock_session)
        helper.create_entity(
            {
                "cluster_name": "deploy",
                "nodes_list": [{"node_serial": "SN1"}, {"node_serial": "SN2"}],
                "skip_cluster_creation": True,
            }
        )
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert "cluster_size" not in payload
        assert "cluster_external_ip" not in payload

    def test_empty_response_raises(self, mock_session):
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1"}, {"node_serial": "SN2"}]},
            None,
        ]
        helper = self._make_helper(mock_session)
        with pytest.raises(RuntimeError, match="Empty response"):
            helper.create_entity(
                {
                    "cluster_name": "deploy",
                    "nodes_list": [{"node_serial": "SN1"}, {"node_serial": "SN2"}],
                }
            )

    def test_missing_nodes_list_raises(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="nodes_list"):
            helper.create_entity({"cluster_name": "deploy"})

    # --- update / delete ---

    def test_update_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.update_entity("id1", {})

    def test_delete_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.delete_entity("id1")

    # --- list / get ---

    def test_list_entities(self, mock_session):
        mock_session.post.return_value = {
            "imaged_clusters": [
                {"cluster_name": "d1", "imaged_cluster_uuid": "u1"},
            ]
        }
        helper = self._make_helper(mock_session)
        assert len(helper.list_entities()) == 1

    def test_get_entity_by_ext_id(self, mock_session):
        mock_session.post.return_value = {
            "imaged_clusters": [
                {"cluster_name": "d1", "imaged_cluster_uuid": "u1"},
            ]
        }
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("u1")["extId"] == "u1"
        assert helper.get_entity_by_ext_id("nonexistent") is None


# ===================================================================
# GenerateFcApiKeyHelper
# ===================================================================


class TestGenerateFcApiKeyHelper:
    def _make_helper(self, session):
        from ztf.helpers.generate_fc_api_key import GenerateFcApiKeyHelper

        return GenerateFcApiKeyHelper(session=session)

    def test_create_api_key_success(self, mock_session):
        mock_session.post.side_effect = [
            {".return": True},
            {"api_keys": []},
            {"api_key": "secret-key-value"},
        ]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity({"alias": "my-key"})
        assert ext_id == "my-key"

    def test_create_api_key_alias_already_exists(self, mock_session):
        mock_session.post.side_effect = [
            {".return": True},
            {"api_keys": [{"alias": "my-key"}]},
        ]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity({"alias": "my-key"})
        assert ext_id == "my-key"
        assert mock_session.post.call_count == 2

    def test_create_api_key_fc_disabled_raises(self, mock_session):
        mock_session.post.side_effect = [
            {".return": False},
            {"api_keys_missing": True},
        ]
        helper = self._make_helper(mock_session)
        with pytest.raises(RuntimeError, match="not enabled"):
            helper.create_entity({"alias": "my-key"})

    def test_create_api_key_fc_check_fails_returns_disabled(self, mock_session):
        mock_session.post.side_effect = Exception("connection refused")
        helper = self._make_helper(mock_session)
        with pytest.raises(RuntimeError, match="not enabled"):
            helper.create_entity({"alias": "my-key"})

    def test_create_api_key_missing_alias_raises(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="alias"):
            helper.create_entity({})

    def test_create_api_key_fc_alias_key_name_accepted(self, mock_session):
        mock_session.post.side_effect = [
            {".return": True},
            {"api_keys": []},
            {"api_key": "val"},
        ]
        helper = self._make_helper(mock_session)
        ext_id = helper.create_entity({"fc_alias_key_name": "alt-key"})
        assert ext_id == "alt-key"

    def test_create_api_key_empty_response_raises(self, mock_session):
        mock_session.post.side_effect = [
            {".return": True},
            {"api_keys": []},
            {},
        ]
        helper = self._make_helper(mock_session)
        with pytest.raises(RuntimeError, match="Failed to generate"):
            helper.create_entity({"alias": "k1"})

    # --- list / get ---

    def test_list_entities(self, mock_session):
        mock_session.post.return_value = {
            "api_keys": [
                {"alias": "k1"},
                {"alias": "k2"},
            ]
        }
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert len(result) == 2
        assert result[0]["alias"] == "k1"

    def test_list_entities_with_filter(self, mock_session):
        mock_session.post.return_value = {
            "api_keys": [
                {"alias": "k1"},
                {"alias": "k2"},
            ]
        }
        helper = self._make_helper(mock_session)
        result = helper.list_entities(custom_filter={"alias": "k2"})
        assert len(result) == 1

    def test_get_entity_by_ext_id_found(self, mock_session):
        mock_session.post.return_value = {"api_keys": [{"alias": "k1"}]}
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("k1") is not None

    def test_get_entity_by_ext_id_not_found(self, mock_session):
        mock_session.post.return_value = {"api_keys": []}
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("nope") is None

    # --- update / delete ---

    def test_update_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.update_entity("k1", {})

    def test_delete_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.delete_entity("k1")


# ===================================================================
# UpdateCvmFoundationHelper
# ===================================================================


class TestUpdateCvmFoundationHelper:
    def _make_helper(self, session, data=None):
        from ztf.helpers.update_cvm_foundation import UpdateCvmFoundationHelper

        return UpdateCvmFoundationHelper(session=session, data=data or {})

    @patch("ztf.helpers.update_cvm_foundation.SSHCvm")
    def test_create_entity_success(self, MockSSHCvm, mock_session):
        mock_ssh = MagicMock()
        mock_ssh.update_resolv_conf.return_value = (True, "")
        mock_ssh.update_cvm_foundation.return_value = (True, "")
        MockSSHCvm.return_value = mock_ssh

        helper = self._make_helper(
            mock_session,
            data={
                "credentials": {
                    "cvm_creds": {"username": "nutanix", "password": "pass123"}
                }
            },
        )
        ext_id = helper.create_entity(
            {
                "cvm_ip": "10.0.0.1",
                "cvm_credential": "cvm_creds",
                "foundation_build_url": "http://example.com/foundation.tar.gz",
                "foundation_version": "5.5",
                "nameserver": "8.8.8.8",
            }
        )
        assert ext_id == "10.0.0.1"
        mock_ssh.update_resolv_conf.assert_called_once_with("8.8.8.8")
        mock_ssh.update_cvm_foundation.assert_called_once_with(
            foundation_url_path="http://example.com/foundation.tar.gz",
            downgrade=False,
        )
        mock_ssh.close.assert_called()

    @patch("ztf.helpers.update_cvm_foundation.SSHCvm")
    def test_create_entity_downgrade(self, MockSSHCvm, mock_session):
        mock_ssh = MagicMock()
        mock_ssh.update_cvm_foundation.return_value = (True, "")
        MockSSHCvm.return_value = mock_ssh

        helper = self._make_helper(
            mock_session,
            data={
                "credentials": {
                    "cvm_creds": {"username": "nutanix", "password": "pass123"}
                }
            },
        )
        helper.create_entity(
            {
                "cvm_ip": "10.0.0.1",
                "cvm_credential": "cvm_creds",
                "foundation_build_url": "http://example.com/foundation.tar.gz",
                "foundation_version": "5.5",
                "downgrade": True,
            }
        )
        mock_ssh.update_cvm_foundation.assert_called_once_with(
            foundation_url_path="http://example.com/foundation.tar.gz",
            downgrade=True,
        )

    @patch("ztf.helpers.update_cvm_foundation.SSHCvm")
    def test_create_entity_ssh_failure_raises(self, MockSSHCvm, mock_session):
        mock_ssh = MagicMock()
        mock_ssh.update_cvm_foundation.return_value = (False, "SSH timeout")
        MockSSHCvm.return_value = mock_ssh

        helper = self._make_helper(
            mock_session,
            data={
                "credentials": {
                    "cvm_creds": {"username": "nutanix", "password": "pass123"}
                }
            },
        )
        with pytest.raises(Exception, match="Failed to update CVM foundation"):
            helper.create_entity(
                {
                    "cvm_ip": "10.0.0.1",
                    "cvm_credential": "cvm_creds",
                    "foundation_build_url": "http://example.com/foundation.tar.gz",
                    "foundation_version": "5.5",
                }
            )
        mock_ssh.close.assert_called()

    @patch("ztf.helpers.update_cvm_foundation.SSHCvm")
    def test_create_entity_ssh_always_closed(self, MockSSHCvm, mock_session):
        """SSH connection is closed even if update_cvm_foundation throws."""
        mock_ssh = MagicMock()
        mock_ssh.update_cvm_foundation.side_effect = Exception("boom")
        MockSSHCvm.return_value = mock_ssh

        helper = self._make_helper(
            mock_session,
            data={
                "credentials": {
                    "cvm_creds": {"username": "nutanix", "password": "pass123"}
                }
            },
        )
        with pytest.raises(Exception):
            helper.create_entity(
                {
                    "cvm_ip": "10.0.0.1",
                    "cvm_credential": "cvm_creds",
                    "foundation_build_url": "http://example.com/f.tar.gz",
                    "foundation_version": "5.5",
                }
            )
        mock_ssh.close.assert_called()

    def test_create_entity_missing_required_fields(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="cvm_ip"):
            helper.create_entity(
                {
                    "cvm_credential": "c",
                    "foundation_build_url": "u",
                    "foundation_version": "v",
                }
            )

    def test_create_entity_inline_credential_dict(self, mock_session):
        """Credential can be passed as inline dict instead of a reference name."""
        with patch("ztf.helpers.update_cvm_foundation.SSHCvm") as MockSSHCvm:
            mock_ssh = MagicMock()
            mock_ssh.update_cvm_foundation.return_value = (True, "")
            MockSSHCvm.return_value = mock_ssh

            helper = self._make_helper(mock_session)
            ext_id = helper.create_entity(
                {
                    "cvm_ip": "10.0.0.1",
                    "cvm_credential": {"username": "admin", "password": "secret"},
                    "foundation_build_url": "http://example.com/f.tar.gz",
                    "foundation_version": "5.5",
                }
            )
            assert ext_id == "10.0.0.1"
            MockSSHCvm.assert_called_once_with("10.0.0.1", "admin", "secret")

    def test_create_entity_unresolvable_credential_raises(self, mock_session):
        helper = self._make_helper(mock_session, data={"credentials": {}})
        with pytest.raises(ValueError, match="Cannot resolve credential"):
            helper.create_entity(
                {
                    "cvm_ip": "10.0.0.1",
                    "cvm_credential": "nonexistent_ref",
                    "foundation_build_url": "http://f.tar.gz",
                    "foundation_version": "5.5",
                }
            )

    def test_update_entity_delegates_to_create(self, mock_session):
        with patch("ztf.helpers.update_cvm_foundation.SSHCvm") as MockSSHCvm:
            mock_ssh = MagicMock()
            mock_ssh.update_cvm_foundation.return_value = (True, "")
            MockSSHCvm.return_value = mock_ssh

            helper = self._make_helper(
                mock_session,
                data={"credentials": {"c": {"username": "u", "password": "p"}}},
            )
            ext_id = helper.update_entity(
                "10.0.0.1",
                {
                    "cvm_credential": "c",
                    "foundation_build_url": "http://f.tar.gz",
                    "foundation_version": "5.5",
                },
            )
            assert ext_id == "10.0.0.1"

    def test_delete_not_implemented(self, mock_session):
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
# FcCreateClusterHelper
# ===================================================================


class TestFcCreateClusterHelper:
    def _make_helper(self, session, config=None):
        from ztf.helpers.fc_create_cluster import FcCreateClusterHelper

        return FcCreateClusterHelper(session=session, data={"config": config or {}})

    def _succeeded_task(self, cluster_ext_id="cluster-uuid-1"):
        return {
            "data": {
                "status": "SUCCEEDED",
                "entitiesAffected": [
                    {"extId": cluster_ext_id, "rel": "clustermgmt:config:cluster"}
                ],
            }
        }

    # --- payload construction ---

    def test_create_entity_builds_expected_payload(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = self._succeeded_task()
        helper = self._make_helper(mock_session)

        ext_id = helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes": [{"extId": "node-1"}, {"extId": "node-2"}],
                "timezone": "UTC",
                "external_ip": "10.0.0.100",
                "cluster_fault_tolerance": "CFT_1N_AND_1D",
                "cvm_dns_servers": "8.8.8.8,8.8.4.4",
                "cvm_ntp_servers": "ntp1,ntp2",
                "hypervisor_ntp_servers": "ntp1,ntp2",
            }
        )

        assert ext_id == "cluster-uuid-1"
        url, kwargs = mock_session.post.call_args[0], mock_session.post.call_args[1]
        assert url[0] == "api/v1/foundation-central/internal/nodes/create-cluster"
        assert kwargs["data"] == {
            "nodes": [{"extId": "node-1"}, {"extId": "node-2"}],
            "clusterName": "c1",
            "timezone": "UTC",
            "externalIp": "10.0.0.100",
            "clusterFaultTolerance": "CFT_1N_AND_1D",
            "cvmDnsServers": "8.8.8.8,8.8.4.4",
            "cvmNtpServers": "ntp1,ntp2",
            "hypervisorNtpServers": "ntp1,ntp2",
        }

    # --- NTNX-Request-Id header ---

    def test_sends_uuid_request_id_header(self, mock_session):
        import uuid as uuid_mod

        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = self._succeeded_task()
        helper = self._make_helper(mock_session)

        helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

        headers = mock_session.post.call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"
        # Raises if FC would reject it as a non-UUID.
        uuid_mod.UUID(headers["NTNX-Request-Id"])

    def test_request_id_is_unique_per_create(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = self._succeeded_task()
        helper = self._make_helper(mock_session)

        body = {"cluster_name": "c1", "nodes": ["node-1"]}
        helper.create_entity(body)
        helper.create_entity(body)

        first, second = (
            call[1]["headers"]["NTNX-Request-Id"]
            for call in mock_session.post.call_args_list
        )
        assert first != second

    def test_explicit_request_id_is_used(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = self._succeeded_task()
        helper = self._make_helper(mock_session)

        helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes": ["node-1"],
                "request_id": "15810e6a-5163-4025-becd-017ff20188eb",
            }
        )

        headers = mock_session.post.call_args[1]["headers"]
        assert headers["NTNX-Request-Id"] == "15810e6a-5163-4025-becd-017ff20188eb"

    def test_non_uuid_request_id_raises(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="valid UUID"):
            helper.create_entity(
                {"cluster_name": "c1", "nodes": ["node-1"], "request_id": "not-a-uuid"}
            )
        mock_session.post.assert_not_called()

    def test_optional_fields_are_omitted_when_absent(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = self._succeeded_task()
        helper = self._make_helper(mock_session)

        helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

        payload = mock_session.post.call_args[1]["data"]
        assert payload == {"nodes": [{"extId": "node-1"}], "clusterName": "c1"}

    def test_node_extids_accept_strings_and_dicts(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = self._succeeded_task()
        helper = self._make_helper(mock_session)

        helper.create_entity(
            {"cluster_name": "c1", "nodes": ["node-1", {"ext_id": "node-2"}]}
        )

        payload = mock_session.post.call_args[1]["data"]
        assert payload["nodes"] == [{"extId": "node-1"}, {"extId": "node-2"}]

    def test_server_lists_are_joined(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = self._succeeded_task()
        helper = self._make_helper(mock_session)

        helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes": ["node-1"],
                "cvm_dns_servers": ["8.8.8.8", "8.8.4.4"],
            }
        )

        payload = mock_session.post.call_args[1]["data"]
        assert payload["cvmDnsServers"] == "8.8.8.8,8.8.4.4"

    def test_missing_cluster_name_raises(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="cluster_name"):
            helper.create_entity({"nodes": ["node-1"]})

    def test_missing_nodes_raises(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="nodes"):
            helper.create_entity({"cluster_name": "c1"})

    def test_node_without_ext_id_raises(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="extId"):
            helper.create_entity({"cluster_name": "c1", "nodes": [{"serial": "SN1"}]})

    # --- task handling ---

    def test_empty_response_raises(self, mock_session):
        mock_session.post.return_value = None
        helper = self._make_helper(mock_session)
        with pytest.raises(RuntimeError, match="Empty response"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

    def test_response_without_task_id_raises(self, mock_session):
        mock_session.post.return_value = {"message": "accepted"}
        helper = self._make_helper(mock_session)
        with pytest.raises(RuntimeError, match="No task extId"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

    def test_failed_task_raises(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = {
            "data": {"status": "FAILED", "errorMessages": ["boom"]}
        }
        helper = self._make_helper(mock_session)
        with pytest.raises(RuntimeError, match="FAILED"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

    def test_wait_for_completion_false_returns_task_id(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = {"data": {}}
        helper = self._make_helper(mock_session)

        ext_id = helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes": ["node-1"],
                "wait_for_completion": False,
            }
        )

        assert ext_id == "task-1"
        assert not any(
            "tasks" in str(call.args[0]) for call in mock_session.get.call_args_list
        )

    def test_completion_details_uuid_preferred_over_task_id(self, mock_session):
        """FC create-cluster tasks often omit entitiesAffected and only
        report the real cluster id via completionDetails cluster_uuid.
        The task's own extId (ergon: / ZXJnb24=:) must not be stored."""
        mock_session.post.return_value = {"extId": "ZXJnb24=:task-own-id"}
        mock_session.get.return_value = {
            "data": {
                "status": "SUCCEEDED",
                "extId": "ZXJnb24=:task-own-id",
                "completionDetails": [
                    {"name": "cluster_uuid", "value": "real-cluster-uuid"},
                ],
            }
        }
        helper = self._make_helper(mock_session)

        assert helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]}) == (
            "real-cluster-uuid"
        )

    def test_succeeded_task_resolves_cluster_from_node(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.side_effect = [
            {"data": {}},
            {"data": {"status": "SUCCEEDED"}},
            {"data": {"clusterExtId": "from-node"}},
        ]
        helper = self._make_helper(mock_session)

        assert helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]}) == (
            "from-node"
        )

    def test_node_in_entities_affected_is_not_used_as_cluster_id(self, mock_session):
        """A node extId in entitiesAffected must not be stored as the cluster."""
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.side_effect = [
            {"data": {}},
            {
                "data": {
                    "status": "SUCCEEDED",
                    "entitiesAffected": [
                        {"extId": "node-1", "rel": "lifecycle:config:node"}
                    ],
                }
            },
            {"data": {"clusterExtId": "real-cluster"}},
        ]
        helper = self._make_helper(mock_session)

        assert helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]}) == (
            "real-cluster"
        )

    def test_create_prefers_cluster_when_node_listed_first(self, mock_session):
        """entitiesAffected listing a node before the cluster must store the cluster."""
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.side_effect = [
            {"data": {}},
            {
                "data": {
                    "status": "SUCCEEDED",
                    "entitiesAffected": [
                        {"extId": "node-1", "rel": "lifecycle:config:node"},
                        {"extId": "cluster-1", "rel": "clustermgmt:config:cluster"},
                    ],
                }
            },
        ]
        helper = self._make_helper(mock_session)

        assert helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]}) == (
            "cluster-1"
        )

    def test_succeeded_task_resolves_cluster_by_name(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.side_effect = [
            {"data": {}},
            {"data": {"status": "SUCCEEDED"}},
            {"data": {}},
            {"data": [{"extId": "from-name", "name": "c1"}]},
        ]
        helper = self._make_helper(mock_session)

        assert helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]}) == (
            "from-name"
        )

    def test_succeeded_task_without_cluster_id_raises(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = {"data": {"status": "SUCCEEDED"}}
        helper = self._make_helper(mock_session)

        with pytest.raises(RuntimeError, match="could not be determined"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

    def test_task_path_falls_back_across_versions(self, mock_session):
        from ztf.helpers.fc_create_cluster import FC_TASK_PATHS

        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.side_effect = [
            {"data": {}},
            Exception("404"),
            self._succeeded_task(),
        ]
        helper = self._make_helper(mock_session)

        assert helper.create_entity({"cluster_name": "c1", "nodes": ["n1"]}) == (
            "cluster-uuid-1"
        )
        assert helper._task_path == FC_TASK_PATHS[1]

    def test_skips_create_when_node_already_clustered(self, mock_session):
        mock_session.get.return_value = {"data": {"clusterExtId": "existing-cluster"}}
        helper = self._make_helper(mock_session)

        ext_id = helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

        assert ext_id == "existing-cluster"
        mock_session.post.assert_not_called()

    def test_skips_create_when_all_nodes_share_cluster(self, mock_session):
        mock_session.get.return_value = {"data": {"clusterExtId": "existing-cluster"}}
        helper = self._make_helper(mock_session)

        ext_id = helper.create_entity(
            {"cluster_name": "c1", "nodes": ["node-1", "node-2"]}
        )

        assert ext_id == "existing-cluster"
        mock_session.post.assert_not_called()

    def test_raises_when_nodes_in_different_clusters(self, mock_session):
        mock_session.get.side_effect = [
            {"data": {"clusterExtId": "cluster-a"}},
            {"data": {"clusterExtId": "cluster-b"}},
        ]
        helper = self._make_helper(mock_session)

        with pytest.raises(ValueError, match="different clusters"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["n1", "n2"]})
        mock_session.post.assert_not_called()

    def test_raises_when_some_nodes_clustered(self, mock_session):
        mock_session.get.side_effect = [
            {"data": {"clusterExtId": "cluster-a"}},
            {"data": {}},
        ]
        helper = self._make_helper(mock_session)

        with pytest.raises(ValueError, match="already in cluster"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["n1", "n2"]})
        mock_session.post.assert_not_called()

    def test_poll_settings_prefer_body_then_global_config(self, mock_session):
        helper = self._make_helper(
            mock_session,
            config={"task_timeout_seconds": 7200, "task_check_interval_seconds": 60},
        )
        assert helper._poll_settings({}) == (7200, 60)
        assert helper._poll_settings(
            {"timeout_seconds": 60, "poll_interval_seconds": 5}
        ) == (60, 5)

    # --- unsupported operations ---

    def test_update_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.update_entity("id1", {})

    def test_delete_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.delete_entity("id1")

    def test_list_and_get_are_inert(self, mock_session):
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []
        assert helper.get_entity_by_ext_id("id1") is None


class TestFcCreateClusterNodeNormalization:
    """_normalize_nodes input coercion and rejection."""

    def _normalize(self, nodes):
        from ztf.helpers.fc_create_cluster import FcCreateClusterHelper

        return FcCreateClusterHelper._normalize_nodes(nodes)

    def test_bare_string_is_wrapped(self):
        assert self._normalize("node-1") == [{"extId": "node-1"}]

    def test_non_list_input_rejected(self):
        with pytest.raises(ValueError, match="must be a string or a list"):
            self._normalize({"extId": "node-1"})

    def test_unsupported_entry_type_rejected(self):
        with pytest.raises(ValueError, match="Unsupported node entry"):
            self._normalize([42])

    def test_dict_entry_without_ext_id_rejected(self):
        with pytest.raises(ValueError, match="missing an extId"):
            self._normalize([{"serial": "ABC123"}])


class TestFcCreateClusterTaskPolling:
    """The multi-iteration poll loop, its timeout, and task-read failures."""

    def _make_helper(self, session, config=None):
        from ztf.helpers.fc_create_cluster import FcCreateClusterHelper

        return FcCreateClusterHelper(session=session, data={"config": config or {}})

    def test_polls_until_task_leaves_running(self, mock_session):
        """Earlier tests all resolved on the first poll, so the loop body --
        the sleep, the status-change log, and the re-read -- never ran."""
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.side_effect = [
            {"data": {"status": "QUEUED"}},
            {"data": {"status": "RUNNING"}},
            {"data": {"status": "RUNNING"}},
            {
                "data": {
                    "status": "SUCCEEDED",
                    "entitiesAffected": [
                        {"extId": "cluster-1", "rel": "clustermgmt:config:cluster"}
                    ],
                }
            },
        ]
        helper = self._make_helper(mock_session)

        with patch("ztf.helpers.fc_create_cluster.time.sleep") as sleep:
            ext_id = helper.create_entity(
                {
                    "cluster_name": "c1",
                    "nodes": ["node-1"],
                    "poll_interval_seconds": 7,
                }
            )

        assert ext_id == "cluster-1"
        # First GET is the pre-create "already clustered?" probe, leaving
        # three poll iterations: the two non-terminal ones sleep, the
        # SUCCEEDED one returns immediately.
        assert sleep.call_count == 2
        assert {c.args[0] for c in sleep.call_args_list} == {7}

    def test_status_change_is_logged_once_per_transition(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.side_effect = [
            {"data": {"status": "RUNNING"}},
            {"data": {"status": "RUNNING"}},
            {
                "data": {
                    "status": "SUCCEEDED",
                    "entitiesAffected": [{"extId": "cluster-1", "rel": "cluster"}],
                }
            },
        ]
        helper = self._make_helper(mock_session)
        helper.logger = MagicMock()

        with patch("ztf.helpers.fc_create_cluster.time.sleep"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

        statuses = [
            c.args[0]
            for c in helper.logger.info.call_args_list
            if "Cluster-create task" in str(c.args[0])
        ]
        assert len(statuses) == 2

    def test_poll_timeout_raises(self, mock_session):
        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.return_value = {"data": {"status": "RUNNING"}}
        helper = self._make_helper(mock_session)

        # monotonic: pre-create probe, then deadline calc, then one loop
        # check that has already passed the deadline.
        with (
            patch("ztf.helpers.fc_create_cluster.time.sleep"),
            patch(
                "ztf.helpers.fc_create_cluster.time.monotonic",
                side_effect=[0, 1, 2, 9999],
            ),
            pytest.raises(RuntimeError, match="did not finish within"),
        ):
            helper.create_entity(
                {
                    "cluster_name": "c1",
                    "nodes": ["node-1"],
                    "timeout_seconds": 60,
                }
            )

    def test_task_read_failure_on_every_version_raises(self, mock_session):
        from ztf.helpers.fc_create_cluster import FC_TASK_PATHS

        mock_session.post.return_value = {"extId": "task-1"}
        mock_session.get.side_effect = [
            {"data": {}},
            *[Exception("boom") for _ in FC_TASK_PATHS],
        ]
        helper = self._make_helper(mock_session)

        with pytest.raises(RuntimeError, match="Unable to read task"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

    def test_post_failure_is_logged_and_reraised(self, mock_session):
        mock_session.get.return_value = {"data": {}}
        mock_session.post.side_effect = Exception("FC-10001")
        helper = self._make_helper(mock_session)
        helper.logger = MagicMock()

        with pytest.raises(Exception, match="FC-10001"):
            helper.create_entity({"cluster_name": "c1", "nodes": ["node-1"]})

        assert helper.logger.error.called


class TestFcCreateClusterExtIdFromTask:
    """_cluster_ext_id_from_task picks the cluster id out of a task."""

    def _pick(self, task):
        from ztf.helpers.fc_create_cluster import FcCreateClusterHelper

        return FcCreateClusterHelper._cluster_ext_id_from_task(task)

    def test_prefers_cluster_rel_over_other_entities(self):
        task = {
            "entitiesAffected": [
                {"extId": "node-1", "rel": "lifecycle:config:node"},
                {"extId": "cluster-1", "rel": "clustermgmt:config:cluster"},
            ]
        }
        assert self._pick(task) == "cluster-1"

    def test_falls_back_to_completion_details_when_no_cluster_rel(self):
        task = {
            "entitiesAffected": [{"uuid": "node-1", "rel": "other:thing"}],
            "completionDetails": [{"name": "cluster_uuid", "value": "cluster-1"}],
        }
        assert self._pick(task) == "cluster-1"

    def test_non_cluster_entities_are_not_used_as_cluster_id(self):
        task = {
            "entitiesAffected": [
                {"extId": "node-1", "rel": "lifecycle:config:node"},
            ]
        }
        assert self._pick(task) is None

    def test_single_dict_entities_affected_is_accepted(self):
        task = {"entitiesAffected": {"extId": "cluster-1", "rel": "cluster"}}
        assert self._pick(task) == "cluster-1"

    def test_non_dict_entries_are_skipped(self):
        task = {"entitiesAffected": ["junk", {"ext_id": "cluster-1", "rel": "cluster"}]}
        assert self._pick(task) == "cluster-1"

    def test_snake_case_completion_details_are_read(self):
        task = {"completion_details": [{"key": "cluster_uuid", "value": "cluster-1"}]}
        assert self._pick(task) == "cluster-1"

    def test_single_dict_completion_details_is_accepted(self):
        task = {"completionDetails": {"name": "cluster_uuid", "value": "cluster-1"}}
        assert self._pick(task) == "cluster-1"

    def test_cluster_extid_named_detail_is_matched(self):
        task = {"completionDetails": [{"name": "clusterExtId", "value": "cluster-1"}]}
        assert self._pick(task) == "cluster-1"

    def test_unrelated_uuid_is_only_a_last_resort(self):
        """A non-cluster *_uuid is accepted only when nothing better exists,
        and a cluster-named detail always wins regardless of ordering."""
        assert (
            self._pick({"completionDetails": [{"name": "foo_uuid", "value": "x"}]})
            == "x"
        )
        task = {
            "completionDetails": [
                {"name": "foo_uuid", "value": "x"},
                {"name": "cluster_uuid", "value": "cluster-1"},
            ]
        }
        assert self._pick(task) == "cluster-1"

    def test_na_and_empty_values_are_ignored(self):
        task = {
            "completionDetails": [
                {"name": "cluster_uuid", "value": "N/A"},
                {"name": "other_uuid", "value": ""},
            ]
        }
        assert self._pick(task) is None

    def test_malformed_shapes_return_none(self):
        assert self._pick({"completionDetails": "nonsense"}) is None
        assert self._pick({"completionDetails": ["junk"]}) is None
        assert self._pick({}) is None


class TestFcCreateClusterExtIdLookup:
    """Node- and name-based recovery when the task omits the cluster id."""

    def _make_helper(self, session):
        from ztf.helpers.fc_create_cluster import FcCreateClusterHelper

        return FcCreateClusterHelper(session=session, data={})

    def test_nested_cluster_object_on_node_is_read(self, mock_session):
        mock_session.get.return_value = {"data": {"cluster": {"extId": "cluster-1"}}}
        helper = self._make_helper(mock_session)
        assert helper._cluster_ext_id_from_node("node-1") == "cluster-1"

    def test_node_read_failure_on_every_version_returns_none(self, mock_session):
        from ztf.helpers.fc_create_cluster import FC_NODE_PATHS

        mock_session.get.side_effect = [Exception("404") for _ in FC_NODE_PATHS]
        helper = self._make_helper(mock_session)
        assert helper._cluster_ext_id_from_node("node-1") is None

    def test_cluster_list_failure_on_every_version_returns_none(self, mock_session):
        from ztf.helpers.fc_create_cluster import FC_CLUSTER_PATHS

        mock_session.get.side_effect = [Exception("404") for _ in FC_CLUSTER_PATHS]
        helper = self._make_helper(mock_session)
        assert helper._cluster_ext_id_by_name("c1") is None

    def test_cluster_lookup_by_name_skips_other_names(self, mock_session):
        mock_session.get.return_value = {
            "data": [
                {"extId": "other", "name": "not-c1"},
                {"extId": "cluster-1", "name": "c1"},
            ]
        }
        helper = self._make_helper(mock_session)
        assert helper._cluster_ext_id_by_name("c1") == "cluster-1"

    def test_cluster_lookup_ignores_non_dict_rows(self, mock_session):
        mock_session.get.return_value = {"data": ["junk", {"extId": "c", "name": "c1"}]}
        helper = self._make_helper(mock_session)
        assert helper._cluster_ext_id_by_name("c1") == "c"

    def test_cluster_lookup_no_match_returns_none(self, mock_session):
        mock_session.get.return_value = {"data": []}
        helper = self._make_helper(mock_session)
        assert helper._cluster_ext_id_by_name("c1") is None

    def test_cluster_name_quotes_are_escaped_for_odata(self, mock_session):
        mock_session.get.return_value = {"data": []}
        helper = self._make_helper(mock_session)
        helper._cluster_ext_id_by_name("o'brien")
        params = mock_session.get.call_args[1]["params"]
        assert params["$filter"] == "name eq 'o''brien'"

    def test_nodes_without_ext_id_are_skipped(self, mock_session):
        """_existing_cluster_ext_id / _resolve_cluster_ext_id defend against
        entries that carry no extId even though _normalize_nodes rejects them."""
        helper = self._make_helper(mock_session)
        assert helper._existing_cluster_ext_id([{}, "not-a-dict"]) is None
        mock_session.get.return_value = {"data": []}
        assert helper._resolve_cluster_ext_id("c1", [{}, "not-a-dict"]) is None

    def test_unwrap_data_handles_non_dict_response(self, mock_session):
        helper = self._make_helper(mock_session)
        assert helper._unwrap_data(["not", "a", "dict"]) == {}
        assert helper._unwrap_data({"status": "OK"}) == {"status": "OK"}

    def test_ext_id_from_ref_returns_none_when_absent(self):
        from ztf.helpers.fc_create_cluster import FcCreateClusterHelper

        assert FcCreateClusterHelper._ext_id_from_ref({"rel": "cluster"}) is None


# ===================================================================
# custom_helpers registry
# ===================================================================


class TestCustomHelpersRegistry:
    def test_registry_has_all_entries(self):
        from ztf.custom_helpers import custom_helpers_registry

        # We have 5 FC helpers registered
        assert len(custom_helpers_registry) >= 5

    def test_registry_keys(self):
        from ztf.custom_helpers import custom_helpers_registry

        expected = {
            "fc_v1_cluster",
            "fc_create_cluster",
            "fc_v1_imaging",
            "generate_fc_api_key",
            "update_cvm_foundation",
            "fc_v1_image_upload",
        }
        actual = set(custom_helpers_registry.keys())
        assert expected.issubset(actual), f"Missing keys: {expected - actual}"

    def test_registry_classes_importable(self):
        """Every class referenced in the registry can be imported."""
        import importlib

        from ztf.custom_helpers import custom_helpers_registry

        for _name, entry in custom_helpers_registry.items():
            mod = importlib.import_module(entry["helper_module"])
            cls = getattr(mod, entry["helper_class"])
            assert cls is not None, (
                f"Failed to import {entry['helper_class']} from {entry['helper_module']}"
            )


# ===================================================================
# SSHCvm (key hardened methods)
# ===================================================================


class TestSSHCvm:
    def test_update_resolv_conf_rejects_invalid_ip(self):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, error = ssh.update_resolv_conf("not-an-ip")
        assert success is False
        assert "Invalid nameserver" in error

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_execute_command_reads_stdout_before_exit_status(self, mock_paramiko):
        """Ensure stdout/stderr are read before recv_exit_status to prevent deadlock."""
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        ssh.client = None
        success, output = ssh._execute_command("echo hello")

        assert success is True
        assert output == "output"
        mock_stdout.read.assert_called_once()
        mock_stderr.read.assert_called_once()
        mock_stdout.channel.recv_exit_status.assert_called_once()


# ===================================================================
# Entity base class
# ===================================================================


class TestEntityBase:
    def test_invalid_http_method_raises_valueerror(self, mock_session):
        from ztf.helpers.entity import Entity

        entity = Entity(session=mock_session, resource_type="/test")
        with pytest.raises(ValueError, match="Invalid HTTP method"):
            entity.get_response("/test", method="INVALID")


# ===================================================================
# FcImageUploadHelper
# ===================================================================


class TestFcImageUploadHelper:
    def _make_helper(self, session, data=None):
        from ztf.helpers.fc_v1_image_upload import FcImageUploadHelper

        return FcImageUploadHelper(session=session, data=data or {})

    def test_registered_in_custom_helpers(self):
        from ztf.custom_helpers import custom_helpers_registry

        assert "fc_v1_image_upload" in custom_helpers_registry
        entry = custom_helpers_registry["fc_v1_image_upload"]
        assert entry["helper_class"] == "FcImageUploadHelper"
        assert entry["helper_module"] == "ztf.helpers.fc_v1_image_upload"

    def test_registered_in_entity_map(self):
        from ztf.entity_wrapper.entity_map import entity_map

        assert "fc_v1_image_upload" in entity_map
        cfg = entity_map["fc_v1_image_upload"]
        assert cfg["namespace"] == "foundation_central"
        assert cfg["use_ztf_helper"] is True
        assert cfg["create_supported"] is True
        assert cfg["delete_supported"] is True
        assert cfg["update_supported"] is False
        assert cfg["update_method_name"] == ""
        assert "fc_ip" not in cfg["helper_schema"]
        assert "fc_credential" not in cfg["helper_schema"]
        assert "image_uuid" not in cfg["helper_schema"]
        assert "image_extId" in cfg["helper_schema"]
        assert cfg["helper_schema"]["image_extId"]["required"] is False

    def test_create_entity_missing_image_ext_id(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="image_extId"):
            helper.create_entity({"image_path": "/tmp/image.iso"})

    def test_create_entity_no_paths_raises(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="metadata_path.*image_path"):
            helper.create_entity({"image_extId": "abc-123"})

    def test_upload_metadata_file_not_found(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(FileNotFoundError, match="Metadata file not found"):
            helper.create_entity(
                {
                    "image_extId": "abc-123",
                    "metadata_path": "/nonexistent/metadata.json",
                }
            )

    def test_upload_metadata_success(self, mock_session, tmp_path):
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text('{"version_id": "test"}')
        mock_session.post.return_value = {"status": "ok"}

        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "image_extId": "abc-123",
                "metadata_path": str(meta_file),
            }
        )

        assert result == "abc-123"
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args[1]
        assert call_args["headers"]["Content-Type"] == "application/octet-stream"
        assert call_args["jsonify"] is False

    def test_upload_image_file_not_found(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(FileNotFoundError, match="Image file not found"):
            helper.create_entity(
                {
                    "image_extId": "abc-123",
                    "image_path": "/nonexistent/image.tar",
                }
            )

    def test_upload_image_success(self, mock_session, tmp_path):
        img_file = tmp_path / "image.tar"
        img_file.write_bytes(b"\x00" * 1024)
        mock_session.post.return_value = {"status": "ok"}

        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "image_extId": "img-456",
                "image_path": str(img_file),
            }
        )

        assert result == "img-456"
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args[1]
        assert call_args["headers"]["Content-Type"] == "application/octet-stream"
        assert call_args["jsonify"] is False

    def test_upload_image_connection_failure(self, mock_session, tmp_path):
        img_file = tmp_path / "image.tar"
        img_file.write_bytes(b"\x00" * 1024)
        mock_session.post.side_effect = Exception("Connection failed")

        helper = self._make_helper(mock_session)
        with pytest.raises(Exception, match="Connection failed"):
            helper.create_entity(
                {
                    "image_extId": "img-456",
                    "image_path": str(img_file),
                }
            )

    def test_upload_image_http_error(self, mock_session, tmp_path):
        from ztf.helpers.utils.exception_utils import RestError

        img_file = tmp_path / "image.tar"
        img_file.write_bytes(b"\x00" * 1024)
        mock_session.post.side_effect = RestError("HTTP 400 Bad Request", "HTTPError")

        helper = self._make_helper(mock_session)
        with pytest.raises(RestError, match="HTTP 400"):
            helper.create_entity(
                {
                    "image_extId": "img-456",
                    "image_path": str(img_file),
                }
            )

    def test_create_entity_full_upload(self, mock_session, tmp_path):
        """Metadata and image binary both upload on the domain session."""
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text('{"version_id": "test"}')
        img_file = tmp_path / "image.tar"
        img_file.write_bytes(b"\x00" * 1024)
        mock_session.post.return_value = {"status": "ok"}

        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "image_extId": "img-uuid-456",
                "metadata_path": str(meta_file),
                "image_path": str(img_file),
            }
        )

        assert result == "img-uuid-456"
        assert mock_session.post.call_count == 2

    def test_generated_example_yaml_comments_optional_image_ext_id(
        self, mock_session, tmp_path
    ):
        """ztf examples comments optional image_extId; runtime still requires it."""
        import yaml

        from ztf.entity_wrapper.entity_map import entity_map
        from ztf.generate_examples import _generate_custom_helper_yaml

        yaml_str = _generate_custom_helper_yaml(
            "fc_v1_image_upload", entity_map["fc_v1_image_upload"]
        )
        parsed = yaml.safe_load(yaml_str)
        body = parsed["domains"]["example_domain"]["resources"]["fc_v1_image_upload"][
            "my_fc_v1_image_upload"
        ]["body"]
        assert "image_extId" not in body, yaml_str
        assert "# image_extId:" in yaml_str

        image_path = tmp_path / "image.iso"
        metadata_path = tmp_path / "metadata.json"
        image_path.write_bytes(b"\x00")
        metadata_path.write_text("{}")
        body["image_path"] = str(image_path)
        body["metadata_path"] = str(metadata_path)

        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="image_extId"):
            helper.create_entity(body)

        body["image_extId"] = "img-from-fc-image"
        mock_session.post.return_value = {"status": "ok"}
        assert helper.create_entity(body) == "img-from-fc-image"

    def test_delete_success(self, mock_session):
        mock_session.delete.return_value = {}
        helper = self._make_helper(mock_session)
        result = helper.delete_entity("img-123")
        assert result is True
        mock_session.delete.assert_called_once()

    def test_delete_error_returns_false(self, mock_session):
        mock_session.delete.side_effect = Exception("Connection failed")
        helper = self._make_helper(mock_session)
        result = helper.delete_entity("img-123")
        assert result is False

    def test_list_entities_success(self, mock_session):
        mock_session.get.return_value = {"data": [{"uuid": "a"}, {"uuid": "b"}]}
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert len(result) == 2

    def test_list_entities_empty(self, mock_session):
        mock_session.get.return_value = {"data": []}
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_list_entities_error(self, mock_session):
        mock_session.get.side_effect = Exception("connection error")
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_list_entities_non_dict_response(self, mock_session):
        mock_session.get.return_value = "<Response [200]>"
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_list_entities_none_custom_filter(self, mock_session):
        mock_session.get.return_value = {"data": [{"name": "img1"}]}
        helper = self._make_helper(mock_session)
        result = helper.list_entities(custom_filter=None)
        assert len(result) == 1

    def test_get_entity_by_ext_id_success(self, mock_session):
        mock_session.get.return_value = {"uuid": "img-1", "name": "test"}
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("img-1")
        assert result is not None
        assert result["uuid"] == "img-1"

    def test_get_entity_by_ext_id_error(self, mock_session):
        mock_session.get.side_effect = Exception("not found")
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("img-1") is None

    def test_get_entity_by_ext_id_non_dict_response(self, mock_session):
        mock_session.get.return_value = "<Response [200]>"
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("img-1") is None

    def test_update_entity_not_implemented(self, mock_session):
        helper = self._make_helper(mock_session)
        with pytest.raises(NotImplementedError):
            helper.update_entity("existing-uuid", {"image_path": "/tmp/image.tar"})

    def test_list_entities_data_not_list(self, mock_session):
        mock_session.get.return_value = {"data": {"unexpected": True}}
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_upload_metadata_non_dict_response(self, mock_session, tmp_path):
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text('{"version_id": "test"}')
        mock_session.post.return_value = "<Response [200]>"

        helper = self._make_helper(mock_session)
        result = helper._upload_metadata("img-123", str(meta_file))
        assert result == {"status": "ok"}

    def test_upload_image_non_dict_response(self, mock_session, tmp_path):
        img_file = tmp_path / "image.tar"
        img_file.write_bytes(b"\x00" * 1024)
        mock_session.post.return_value = "<Response [200]>"

        helper = self._make_helper(mock_session)
        result = helper._upload_image("img-123", str(img_file))
        assert result == {"status": "ok"}

    def test_upload_metadata_dict_response(self, mock_session, tmp_path):
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text('{"version_id": "test"}')
        mock_session.post.return_value = {"MetadataStatus": "FILE_AVAILABLE"}

        helper = self._make_helper(mock_session)
        result = helper._upload_metadata("img-123", str(meta_file))
        assert result == {"MetadataStatus": "FILE_AVAILABLE"}

    def test_upload_image_dict_response(self, mock_session, tmp_path):
        img_file = tmp_path / "image.tar"
        img_file.write_bytes(b"\x00" * 1024)
        mock_session.post.return_value = {"FileStatus": "FILE_AVAILABLE"}

        helper = self._make_helper(mock_session)
        result = helper._upload_image("img-123", str(img_file))
        assert result == {"FileStatus": "FILE_AVAILABLE"}
