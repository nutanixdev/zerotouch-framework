"""
Unit tests for SSH-based helpers: UpdateCvmFoundationHelper.

Run: pytest tests/test_ssh_helpers.py -v

These tests mock SSHCvm so no real SSH connections are needed.
"""

from unittest.mock import MagicMock, patch

import pytest

from ztf.helpers.update_cvm_foundation import UpdateCvmFoundationHelper
from ztf.helpers.utils.rest_utils import RestAPIUtil


@pytest.fixture
def mock_session():
    return MagicMock(spec=RestAPIUtil)


class TestUpdateCvmFoundationHelper:
    """Tests for UpdateCvmFoundationHelper."""

    @pytest.fixture
    def helper(self, mock_session):
        return UpdateCvmFoundationHelper(
            session=mock_session,
            data={
                "credentials": {
                    "cvm_creds": {"username": "nutanix", "password": "testpass"}
                },
                "config": {},
                "global_config": {},
            },
        )

    def test_create_entity_missing_required_field(self, helper):
        body = {"cvm_ip": "10.0.0.1", "cvm_credential": "cvm_creds"}
        with pytest.raises(ValueError, match="foundation_build_url"):
            helper.create_entity(body)

    @patch("ztf.helpers.update_cvm_foundation.SSHCvm")
    def test_create_entity_calls_ssh_and_returns_cvm_ip(self, mock_ssh_class, helper):
        mock_ssh = MagicMock()
        mock_ssh.update_resolv_conf.return_value = (True, "")
        mock_ssh.update_cvm_foundation.return_value = (True, "")
        mock_ssh_class.return_value = mock_ssh

        body = {
            "cvm_ip": "10.0.0.1",
            "cvm_credential": "cvm_creds",
            "foundation_build_url": "http://example.com/foundation.tar",
            "foundation_version": "7.0.0",
            "nameserver": "8.8.8.8",
        }
        ext_id = helper.create_entity(body)

        assert ext_id == "10.0.0.1"
        mock_ssh.update_resolv_conf.assert_called_once_with("8.8.8.8")
        mock_ssh.update_cvm_foundation.assert_called_once_with(
            foundation_url_path="http://example.com/foundation.tar",
            downgrade=False,
        )
        mock_ssh.close.assert_called_once()

    @patch("ztf.helpers.update_cvm_foundation.SSHCvm")
    def test_create_entity_without_nameserver(self, mock_ssh_class, helper):
        mock_ssh = MagicMock()
        mock_ssh.update_cvm_foundation.return_value = (True, "")
        mock_ssh_class.return_value = mock_ssh

        body = {
            "cvm_ip": "10.0.0.1",
            "cvm_credential": "cvm_creds",
            "foundation_build_url": "http://example.com/foundation.tar",
            "foundation_version": "7.0.0",
        }
        ext_id = helper.create_entity(body)

        assert ext_id == "10.0.0.1"
        mock_ssh.update_resolv_conf.assert_not_called()
        mock_ssh.update_cvm_foundation.assert_called_once_with(
            foundation_url_path="http://example.com/foundation.tar",
            downgrade=False,
        )

    @patch("ztf.helpers.update_cvm_foundation.SSHCvm")
    def test_create_entity_raises_on_ssh_failure(self, mock_ssh_class, helper):
        mock_ssh = MagicMock()
        mock_ssh.update_cvm_foundation.return_value = (False, "Download failed")
        mock_ssh_class.return_value = mock_ssh

        body = {
            "cvm_ip": "10.0.0.1",
            "cvm_credential": "cvm_creds",
            "foundation_build_url": "http://example.com/foundation.tar",
            "foundation_version": "7.0.0",
        }
        with pytest.raises(Exception, match="Failed to update CVM foundation"):
            helper.create_entity(body)
        mock_ssh.close.assert_called_once()

    def test_create_entity_raises_on_unresolvable_credential(self, helper):
        helper.data = {"credentials": {}, "config": {}, "global_config": {}}
        body = {
            "cvm_ip": "10.0.0.1",
            "cvm_credential": "cvm_creds",
            "foundation_build_url": "http://example.com/foundation.tar",
            "foundation_version": "7.0.0",
        }
        with pytest.raises(ValueError, match="Cannot resolve credential"):
            helper.create_entity(body)
