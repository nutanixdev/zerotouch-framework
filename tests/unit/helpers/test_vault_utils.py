from unittest.mock import MagicMock, patch
from framework.helpers.vault_utils import CyberArk
import pytest

class TestVaultUtils:
    @pytest.fixture
    def cyber_ark(self):
        cyber_ark = CyberArk("example.com", "1234", "cert_file.pem", "cert_key.pem")
        cyber_ark.session = MagicMock()
        return cyber_ark

    @patch("builtins.open")
    def test_generate_auth_token(self, mock_open, cyber_ark):
        cyber_ark.session.post.return_value = "auth_token"
        mock_open.return_value.read.return_value = "password"
        result = cyber_ark.generate_auth_token("user", "password.txt")
        assert result == "auth_token"
        cyber_ark.session.post.assert_called_with(
            "PasswordVault/API/Auth/CyberArk/Logon",
            data={"username": "user", "password": "password"},
            verify="cert_file.pem",
            cert=("cert_file.pem", "cert_key.pem")
        )

    def test_fetch_creds(self, cyber_ark):
        cyber_ark.session.get.return_value = {"Content": "password"}
        result = cyber_ark.fetch_creds("auth_token", "username", "app_id", "safe", "address")
        assert result == "password"
        cyber_ark.session.get.assert_called_with(
            "AIMWebService/api/Accounts?AppId=app_id&Query=Safe=safe;UserName=username;Address=address",
            data={"Authorization": "auth_token"},
            verify="cert_file.pem",
            cert=("cert_file.pem", "cert_key.pem")
        )

    def test_session_log_off(self, cyber_ark):
        cyber_ark.session.post.return_value = None
        cyber_ark.session_log_off()
        cyber_ark.session.post.assert_called_with("PasswordVault/API/Auth/LogOff")



