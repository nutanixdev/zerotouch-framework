"""
Coverage tests for helper utilities: rest_utils, entity, ssh_cvm,
exception_utils, general_utils, log_utils, pe_entity.
"""

import logging
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ===================================================================
# exception_utils
# ===================================================================


class TestExceptionUtils:
    def test_rest_error_defaults(self):
        from ztf.helpers.utils.exception_utils import RestError

        err = RestError()
        assert err.message == "An error occurred with REST API call."
        assert err.error == "RestError"

    def test_rest_error_custom(self):
        from ztf.helpers.utils.exception_utils import RestError

        err = RestError(message="boom", error="Custom", status=500)
        assert err.message == "boom"
        assert err.error == "Custom"
        assert err.status == 500

    def test_response_error_defaults(self):
        from ztf.helpers.utils.exception_utils import ResponseError

        err = ResponseError()
        assert err.message == "An error occurred with REST API response."
        assert err.error == "ResponseError"

    def test_response_error_custom(self):
        from ztf.helpers.utils.exception_utils import ResponseError

        err = ResponseError(message="bad", error="Fail", code=502)
        assert err.message == "bad"
        assert err.error == "Fail"
        assert err.code == 502


# ===================================================================
# general_utils
# ===================================================================


class TestGeneralUtils:
    def test_intersection_dict_match(self):
        from ztf.helpers.utils.general_utils import intersection

        obj = {"a": 1, "b": 2, "c": 3}
        assert intersection(obj, {"a": 1, "b": 2}) is True

    def test_intersection_dict_no_match(self):
        from ztf.helpers.utils.general_utils import intersection

        obj = {"a": 1, "b": 2}
        assert intersection(obj, {"a": 99}) is False

    def test_intersection_nested_dict(self):
        from ztf.helpers.utils.general_utils import intersection

        obj = {"top": {"nested": "value"}}
        assert intersection(obj, {"nested": "value"}) is True

    def test_intersection_list_of_dicts(self):
        from ztf.helpers.utils.general_utils import intersection

        obj = [{"a": 1}, {"b": 2}]
        assert intersection(obj, {"b": 2}) is False

    def test_intersection_non_matching_type(self):
        from ztf.helpers.utils.general_utils import intersection

        assert intersection("string", {"a": 1}) is False


# ===================================================================
# log_utils
# ===================================================================


class TestLogUtils:
    def test_get_logger_returns_logger(self):
        from ztf.helpers.utils.log_utils import get_logger

        log = get_logger("test_module")
        assert isinstance(log, logging.Logger)

    def test_get_logger_with_file(self):
        from ztf.helpers.utils.log_utils import get_logger

        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            log = get_logger("test_file_logger", file_name=f.name)
            assert any(isinstance(h, logging.FileHandler) for h in log.handlers)

    def test_add_file_formatter(self):
        from ztf.helpers.utils.log_utils import add_file_formatter

        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            fh = logging.FileHandler(tmp_path)
            add_file_formatter(fh)
            assert fh.formatter is not None
            assert "%(module)s" in fh.formatter._fmt
            fh.close()
        finally:
            os.unlink(tmp_path)


# ===================================================================
# rest_utils — RestAPIUtil + decorator
# ===================================================================


class TestRestAPIUtil:
    def _make_util(self, **kwargs):
        with patch("ztf.helpers.utils.rest_utils.requests.Session") as MockSess:
            mock_session = MagicMock()
            MockSess.return_value = mock_session
            defaults = {
                "ip_address": "10.0.0.1",
                "user": "admin",
                "pwd": "pass",
            }
            defaults.update(kwargs)
            from ztf.helpers.utils.rest_utils import RestAPIUtil

            util = RestAPIUtil(**defaults)
            return util, mock_session

    def test_init_sets_auth(self):
        util, mock_session = self._make_util()
        assert mock_session.auth is not None

    def test_init_no_auth_when_no_user(self):
        self._make_util(user=None, pwd=None)

    def test_init_custom_headers(self):
        self._make_util(headers={"X-Custom": "val"})

    def test_init_http_unsecured(self):
        util, _ = self._make_util(secured=False)
        assert util.get_protocol() == "http"

    def test_init_with_port(self):
        util, _ = self._make_util(port="9440")
        url = util.prepare_url("api/v1/test")
        assert ":9440" in url

    def test_prepare_url_https(self):
        util, _ = self._make_util()
        url = util.prepare_url("api/v1/test")
        assert url.startswith("https://10.0.0.1")
        assert url.endswith("/api/v1/test")

    def test_get_protocol_https(self):
        util, _ = self._make_util(secured=True)
        assert util.get_protocol() == "https"

    def test_get_protocol_http(self):
        util, _ = self._make_util(secured=False)
        assert util.get_protocol() == "http"


class TestTimeoutHTTPAdapter:
    def test_sets_default_timeout(self):
        from ztf.helpers.utils.rest_utils import TimeoutHTTPAdapter

        adapter = TimeoutHTTPAdapter()
        mock_request = MagicMock()
        with patch.object(
            adapter.__class__.__bases__[0], "send", return_value=MagicMock()
        ) as mock_super:
            adapter.send(mock_request)
            call_kwargs = mock_super.call_args[1]
            assert call_kwargs["timeout"] == (5, 300)

    def test_respects_existing_timeout(self):
        from ztf.helpers.utils.rest_utils import TimeoutHTTPAdapter

        adapter = TimeoutHTTPAdapter()
        mock_request = MagicMock()
        with patch.object(
            adapter.__class__.__bases__[0], "send", return_value=MagicMock()
        ) as mock_super:
            adapter.send(mock_request, timeout=10)
            call_kwargs = mock_super.call_args[1]
            assert call_kwargs["timeout"] == 10


class TestRestApiCallDecorator:
    def _make_mock_response(
        self,
        status=200,
        json_data=None,
        content_type="application/json",
        text="",
        raise_for_status=None,
    ):
        resp = MagicMock()
        resp.status_code = status
        resp.headers = {"Content-Type": content_type}
        resp.url = "https://test/api"
        resp.request = MagicMock()
        resp.request.method = "GET"
        resp.text = text
        resp.content = text.encode("utf-8") if text else b""
        if json_data is not None:
            resp.json.return_value = json_data
        else:
            resp.json.side_effect = ValueError("No JSON")
        if raise_for_status:
            resp.raise_for_status.side_effect = raise_for_status
        else:
            resp.raise_for_status.return_value = None
        return resp

    def test_json_response_success(self):
        from ztf.helpers.utils.rest_utils import rest_api_call

        resp = self._make_mock_response(json_data={"key": "value"})

        @rest_api_call
        def fake_call():
            return resp

        result = fake_call()
        assert result == {"key": "value"}

    def test_non_json_content_type_returns_text(self):
        from ztf.helpers.utils.rest_utils import rest_api_call

        resp = self._make_mock_response(content_type="text/plain", text="plain text")

        @rest_api_call
        def fake_call():
            return resp

        result = fake_call()
        assert result == "plain text"

    def test_non_json_content_parseable_as_json(self):
        from ztf.helpers.utils.rest_utils import rest_api_call

        resp = self._make_mock_response(
            content_type="text/plain", text='{"parsed": true}'
        )

        @rest_api_call
        def fake_call():
            return resp

        result = fake_call()
        assert result == {"parsed": True}

    def test_json_parse_failure_200_returns_response(self):
        from ztf.helpers.utils.rest_utils import rest_api_call

        resp = self._make_mock_response(status=200)
        resp.json.side_effect = ValueError("no json")
        resp.__str__ = lambda self: "<Response [200]>"

        @rest_api_call
        def fake_call():
            return resp

        result = fake_call()
        assert result is resp

    def test_json_parse_failure_500_reraises(self):
        from ztf.helpers.utils.rest_utils import RestError, rest_api_call

        resp = self._make_mock_response(status=500)
        resp.json.side_effect = ValueError("no json")
        resp.__str__ = lambda self: "<Response [500]>"
        resp.raise_for_status.side_effect = Exception("Server Error")

        @rest_api_call
        def fake_call():
            return resp

        with pytest.raises(RestError):
            fake_call()

    def test_401_error_message(self):
        from requests.exceptions import HTTPError

        from ztf.helpers.utils.rest_utils import RestError, rest_api_call

        resp = self._make_mock_response(status=401, json_data={"error": "unauth"})
        resp.raise_for_status.side_effect = HTTPError("401")

        @rest_api_call
        def fake_call():
            return resp

        with pytest.raises(RestError, match="Unauthorized"):
            fake_call()

    def test_500_with_json_error(self):
        from ztf.helpers.utils.rest_utils import RestError, rest_api_call

        resp = self._make_mock_response(status=500, json_data={"detail": "crash"})
        resp.raise_for_status.side_effect = Exception("boom")

        @rest_api_call
        def fake_call():
            return resp

        with pytest.raises(RestError):
            fake_call()

    def test_error_no_response_object(self):
        from ztf.helpers.utils.rest_utils import RestError, rest_api_call

        @rest_api_call
        def fake_call():
            raise Exception("connection refused")

        with pytest.raises(RestError):
            fake_call()

    def test_error_with_text_attribute(self):
        from ztf.helpers.utils.rest_utils import RestError, rest_api_call

        resp = self._make_mock_response(status=503, text="service unavailable")
        resp.json.side_effect = Exception("no json")
        del resp.json
        resp.raise_for_status.side_effect = Exception("fail")

        @rest_api_call
        def fake_call():
            return resp

        with pytest.raises(RestError):
            fake_call()

    def test_response_401_raises_login_failed(self):
        from ztf.helpers.utils.rest_utils import ResponseError, rest_api_call

        resp = self._make_mock_response(status=401, json_data="<Response [401]>")
        resp.raise_for_status.return_value = None

        @rest_api_call
        def fake_call():
            return resp

        with pytest.raises(ResponseError) as exc_info:
            fake_call()
        assert exc_info.value.error == "LoginFailed"

    def test_response_502_raises_bad_gateway(self):
        from ztf.helpers.utils.rest_utils import ResponseError, rest_api_call

        resp = self._make_mock_response(status=502, json_data="<Response [502]>")
        resp.raise_for_status.return_value = None

        @rest_api_call
        def fake_call():
            return resp

        with pytest.raises(ResponseError) as exc_info:
            fake_call()
        assert exc_info.value.error == "BadGateway"


# ===================================================================
# RestAPIUtil — HTTP method integration tests (through decorator)
# ===================================================================


class TestRestAPIUtilMethods:
    """Test post/put/get/delete/patch through the full decorator path."""

    @pytest.fixture
    def util_and_session(self):
        with patch("ztf.helpers.utils.rest_utils.requests.Session") as MockSess:
            mock_session = MagicMock()
            MockSess.return_value = mock_session
            from ztf.helpers.utils.rest_utils import RestAPIUtil

            util = RestAPIUtil(
                ip_address="10.0.0.1", user="admin", pwd="pass", port="9440"
            )
            yield util, mock_session

    def _ok_response(self, json_data=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"Content-Type": "application/json"}
        resp.url = "https://10.0.0.1:9440/api"
        resp.request = MagicMock()
        resp.request.method = "GET"
        resp.json.return_value = json_data if json_data is not None else {"ok": True}
        resp.raise_for_status.return_value = None
        resp.__str__ = lambda self: "<Response [200]>"
        return resp

    def test_post(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.post.return_value = self._ok_response({"created": True})
        result = util.post("api/v1/items", data={"name": "test"})
        assert result == {"created": True}
        mock_session.post.assert_called_once()

    def test_post_no_jsonify(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.post.return_value = self._ok_response()
        util.post("api/v1/items", data={"raw": True}, jsonify=False)

    def test_post_empty_data(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.post.return_value = self._ok_response()
        util.post("api/v1/items")

    def test_put(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.put.return_value = self._ok_response({"updated": True})
        result = util.put("api/v1/items/1", data={"name": "updated"})
        assert result == {"updated": True}

    def test_put_no_jsonify(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.put.return_value = self._ok_response()
        util.put("api/v1/items/1", data={"raw": True}, jsonify=False)

    def test_put_empty_data(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.put.return_value = self._ok_response()
        util.put("api/v1/items/1")

    def test_get(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.get.return_value = self._ok_response({"items": []})
        result = util.get("api/v1/items")
        assert result == {"items": []}

    def test_get_with_data(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.get.return_value = self._ok_response({"items": [1]})
        result = util.get("api/v1/items", data={"filter": "name==x"})
        assert result == {"items": [1]}

    def test_delete(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.delete.return_value = self._ok_response({})
        result = util.delete("api/v1/items/1")
        assert result == {}

    def test_patch(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.patch.return_value = self._ok_response({"patched": True})
        result = util.patch("api/v1/items/1", data={"field": "new"})
        assert result == {"patched": True}

    def test_patch_no_jsonify(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.patch.return_value = self._ok_response()
        util.patch("api/v1/items/1", data={"raw": True}, jsonify=False)

    def test_patch_empty_payload(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.patch.return_value = self._ok_response()
        util.patch("api/v1/items/1")

    def test_post_custom_headers(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.post.return_value = self._ok_response()
        util.post("api/v1/items", headers={"X-Custom": "val"}, data={"x": 1})

    def test_get_custom_headers(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.get.return_value = self._ok_response()
        util.get("api/v1/items", headers={"X-Custom": "val"})

    def test_delete_custom_headers(self, util_and_session):
        util, mock_session = util_and_session
        mock_session.delete.return_value = self._ok_response()
        util.delete("api/v1/items/1", headers={"X-Custom": "val"})

    def test_cached_session(self):
        with patch(
            "ztf.helpers.utils.rest_utils.requests_cache.CachedSession"
        ) as MockCache:
            MockCache.return_value = MagicMock()
            from ztf.helpers.utils.rest_utils import RestAPIUtil

            RestAPIUtil(
                ip_address="10.0.0.1",
                user="admin",
                pwd="pass",
                cache=True,
            )
            MockCache.assert_called_once()


# ===================================================================
# Entity base class
# ===================================================================


class TestEntityClass:
    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    def _make_entity(self, session):
        from ztf.helpers.entity import Entity

        return Entity(session=session, resource_type="/api/v1/test")

    def test_get_response_get(self, mock_session):
        mock_session.get.return_value = {"data": "ok"}
        entity = self._make_entity(mock_session)
        result = entity.get_response("/api/v1/test")
        assert result == {"data": "ok"}

    def test_get_response_post(self, mock_session):
        mock_session.post.return_value = {"created": True}
        entity = self._make_entity(mock_session)
        result = entity.get_response("/api/v1/test", method="POST", data={})
        assert result == {"created": True}

    def test_get_response_put(self, mock_session):
        mock_session.put.return_value = {"updated": True}
        entity = self._make_entity(mock_session)
        result = entity.get_response("/api/v1/test", method="PUT", data={})
        assert result == {"updated": True}

    def test_get_response_patch(self, mock_session):
        mock_session.patch.return_value = {"patched": True}
        entity = self._make_entity(mock_session)
        result = entity.get_response("/api/v1/test", method="PATCH", data={})
        assert result == {"patched": True}

    def test_get_response_delete(self, mock_session):
        mock_session.delete.return_value = {}
        entity = self._make_entity(mock_session)
        result = entity.get_response("/api/v1/test", method="DELETE")
        assert result == {}

    def test_read_get(self, mock_session):
        mock_session.get.return_value = {"entities": [{"id": 1}]}
        entity = self._make_entity(mock_session)
        result = entity.read()
        assert result == [{"id": 1}]

    def test_read_get_with_uuid(self, mock_session):
        mock_session.get.return_value = {"id": 1}
        entity = self._make_entity(mock_session)
        result = entity.read(uuid="abc-123")
        assert result == {"id": 1}

    def test_read_post(self, mock_session):
        mock_session.post.return_value = {"entities": [{"id": 2}]}
        entity = self._make_entity(mock_session)
        result = entity.read(method="POST", data={})
        assert result == [{"id": 2}]

    def test_read_with_endpoint(self, mock_session):
        mock_session.get.return_value = {"data": "ok"}
        entity = self._make_entity(mock_session)
        entity.read(endpoint="sub")

    def test_read_with_query(self, mock_session):
        mock_session.get.return_value = {"data": "ok"}
        entity = self._make_entity(mock_session)
        entity.read(query={"filter": "name==test"})

    def test_read_with_timeout(self, mock_session):
        mock_session.get.return_value = {"data": "ok"}
        entity = self._make_entity(mock_session)
        entity.read(timeout=30)

    def test_read_with_custom_filters(self, mock_session):
        mock_session.get.return_value = {"entities": [{"name": "a"}, {"name": "b"}]}
        entity = self._make_entity(mock_session)
        result = entity.read(custom_filters={"name": "a"})
        assert {"name": "a"} in result

    def test_read_invalid_method(self, mock_session):
        entity = self._make_entity(mock_session)
        with pytest.raises(ValueError, match="Invalid HTTP method"):
            entity.read(method="PATCH")

    def test_read_post_with_timeout(self, mock_session):
        mock_session.post.return_value = {"entities": []}
        entity = self._make_entity(mock_session)
        entity.read(method="POST", data={}, timeout=30)

    def test_create(self, mock_session):
        mock_session.post.return_value = {"id": "new-1"}
        entity = self._make_entity(mock_session)
        result = entity.create(data={"name": "test"})
        assert result == {"id": "new-1"}

    def test_create_with_endpoint_and_query(self, mock_session):
        mock_session.post.return_value = {"id": "new-2"}
        entity = self._make_entity(mock_session)
        entity.create(data={}, endpoint="sub", query={"dry": "true"})

    def test_create_with_timeout(self, mock_session):
        mock_session.post.return_value = {"id": "new-3"}
        entity = self._make_entity(mock_session)
        entity.create(data={}, timeout=60)

    def test_update_put(self, mock_session):
        mock_session.put.return_value = {"updated": True}
        entity = self._make_entity(mock_session)
        result = entity.update(data={"field": "val"})
        assert result == {"updated": True}

    def test_update_put_with_timeout(self, mock_session):
        mock_session.put.return_value = {"updated": True}
        entity = self._make_entity(mock_session)
        entity.update(data={}, timeout=30)

    def test_update_patch(self, mock_session):
        mock_session.patch.return_value = {"patched": True}
        entity = self._make_entity(mock_session)
        result = entity.update(data={}, method="PATCH")
        assert result == {"patched": True}

    def test_update_patch_with_timeout(self, mock_session):
        mock_session.patch.return_value = {"patched": True}
        entity = self._make_entity(mock_session)
        entity.update(data={}, method="PATCH", timeout=30)

    def test_update_with_endpoint_and_query(self, mock_session):
        mock_session.put.return_value = {}
        entity = self._make_entity(mock_session)
        entity.update(data={}, endpoint="sub", query={"x": "1"})

    def test_update_invalid_method(self, mock_session):
        entity = self._make_entity(mock_session)
        with pytest.raises(ValueError, match="Invalid HTTP method"):
            entity.update(data={}, method="DELETE")

    def test_list_entities(self, mock_session):
        mock_session.post.return_value = {"entities": [{"id": 1}, {"id": 2}]}
        entity = self._make_entity(mock_session)
        result = entity.list()
        assert len(result) == 2

    def test_list_with_base_url(self, mock_session):
        mock_session.post.return_value = {"entities": []}
        entity = self._make_entity(mock_session)
        entity.list(use_base_url=True)

    def test_list_with_endpoint(self, mock_session):
        mock_session.post.return_value = {"entities": []}
        entity = self._make_entity(mock_session)
        entity.list(endpoint="sub")

    def test_list_with_query(self, mock_session):
        mock_session.post.return_value = {"entities": []}
        entity = self._make_entity(mock_session)
        entity.list(query={"limit": "10"})

    def test_list_with_timeout(self, mock_session):
        mock_session.post.return_value = {"entities": []}
        entity = self._make_entity(mock_session)
        entity.list(timeout=30)

    def test_list_with_custom_filters(self, mock_session):
        mock_session.post.return_value = {"entities": [{"name": "x"}, {"name": "y"}]}
        entity = self._make_entity(mock_session)
        result = entity.list(custom_filters={"name": "x"})
        assert {"name": "x"} in result

    def test_upload_json(self, mock_session):
        mock_session.post.return_value = {"id": "uploaded"}
        entity = self._make_entity(mock_session)
        result = entity.upload_json(data={"file": "data"})
        assert result == {"id": "uploaded"}

    def test_upload_json_with_all_params(self, mock_session):
        mock_session.post.return_value = {"id": "u2"}
        entity = self._make_entity(mock_session)
        entity.upload_json(
            data={},
            headers={},
            endpoint="sub",
            query={"q": "1"},
            timeout=30,
            jsonify=False,
        )

    def test_upload(self, mock_session):
        mock_session.post.return_value = {"id": "file-1"}
        entity = self._make_entity(mock_session)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test data")
            f.flush()
            tmp_path = f.name
        try:
            entity.upload(source=tmp_path, data={"field": "val"})
        finally:
            os.unlink(tmp_path)

    def test_upload_with_query(self, mock_session):
        mock_session.post.return_value = {}
        entity = self._make_entity(mock_session)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            f.flush()
            tmp_path = f.name
        try:
            entity.upload(source=tmp_path, data={}, query={"x": "1"})
        finally:
            os.unlink(tmp_path)

    def test_delete_entity(self, mock_session):
        mock_session.delete.return_value = {}
        entity = self._make_entity(mock_session)
        entity.delete(uuid="abc-123")

    def test_delete_with_endpoint_and_query(self, mock_session):
        mock_session.delete.return_value = {}
        entity = self._make_entity(mock_session)
        entity.delete(endpoint="sub", query={"force": "true"})

    def test_delete_with_timeout(self, mock_session):
        mock_session.delete.return_value = {}
        entity = self._make_entity(mock_session)
        entity.delete(uuid="x", timeout=10)

    def test_delete_exception_propagates(self, mock_session):
        mock_session.delete.side_effect = Exception("fail")
        entity = self._make_entity(mock_session)
        with pytest.raises(Exception, match="fail"):
            entity.delete(uuid="x")

    def test_get_spec_returns_default(self, mock_session):
        entity = self._make_entity(mock_session)
        spec, error = entity.get_spec()
        assert error is None

    def test_get_spec_with_build_method(self, mock_session):
        entity = self._make_entity(mock_session)
        entity.build_spec_methods["param1"] = lambda spec, config, params: (spec, None)
        spec, error = entity.get_spec(params={"param1": "value"})
        assert error is None

    def test_get_spec_build_method_returns_error(self, mock_session):
        entity = self._make_entity(mock_session)
        entity.build_spec_methods["param1"] = lambda spec, config, params: (
            None,
            "bad param",
        )
        spec, error = entity.get_spec(params={"param1": "value"})
        assert spec is None
        assert error == "bad param"

    def test_build_url_with_query(self, mock_session):
        from ztf.helpers.entity import Entity

        url = Entity._build_url_with_query(
            "/api/v1/test", {"limit": "10", "offset": "0"}
        )
        assert "limit=10" in url
        assert "offset=0" in url

    def test_filter_entities(self, mock_session):
        from ztf.helpers.entity import Entity

        entities = [{"name": "a", "id": 1}, {"name": "b", "id": 2}]
        result = Entity._filter_entities(entities, {"name": "a"})
        assert len(result) == 1

    def test_init_creates_session_when_none(self):
        with patch("ztf.helpers.entity.RestAPIUtil") as MockRest:
            MockRest.return_value = MagicMock()
            from ztf.helpers.entity import Entity

            Entity(ip="10.0.0.1", username="admin", password="pass")
            MockRest.assert_called_once()


# ===================================================================
# PeEntity
# ===================================================================


class TestPeEntity:
    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    def test_pe_entity_init(self, mock_session):
        from ztf.helpers.pe_entity import PeEntity

        pe = PeEntity(session=mock_session)
        assert pe.resource is not None

    def test_get_proxy_endpoint_without_uuid(self, mock_session):
        from ztf.helpers.pe_entity import PeEntity

        pe = PeEntity(session=mock_session)
        result = pe.get_proxy_endpoint("sub")
        assert result == "sub"

    def test_get_proxy_endpoint_with_uuid(self, mock_session):
        from ztf.helpers.pe_entity import PeEntity

        pe = PeEntity(session=mock_session, proxy_cluster_uuid="c-uuid")
        result = pe.get_proxy_endpoint("sub")
        assert "proxyClusterUuid=c-uuid" in result
        assert "?" in result

    def test_get_proxy_endpoint_with_existing_query(self, mock_session):
        from ztf.helpers.pe_entity import PeEntity

        pe = PeEntity(session=mock_session, proxy_cluster_uuid="c-uuid")
        result = pe.get_proxy_endpoint("sub?filter=name")
        assert "&proxyClusterUuid=c-uuid" in result

    def test_pe_read(self, mock_session):
        mock_session.get.return_value = {"entities": []}
        from ztf.helpers.pe_entity import PeEntity

        pe = PeEntity(session=mock_session)
        pe.read()

    def test_pe_create(self, mock_session):
        mock_session.post.return_value = {"id": "1"}
        from ztf.helpers.pe_entity import PeEntity

        pe = PeEntity(session=mock_session)
        pe.create(data={"name": "test"})

    def test_pe_update(self, mock_session):
        mock_session.put.return_value = {}
        from ztf.helpers.pe_entity import PeEntity

        pe = PeEntity(session=mock_session)
        pe.update(data={})

    def test_pe_delete(self, mock_session):
        mock_session.delete.return_value = {}
        from ztf.helpers.pe_entity import PeEntity

        pe = PeEntity(session=mock_session)
        pe.delete()


# ===================================================================
# SSHCvm
# ===================================================================


class TestSSHCvmCoverage:
    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_connect_success(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        assert ssh._connect() is True
        mock_client.connect.assert_called_once()

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_connect_failure(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("timeout")
        mock_paramiko.SSHClient.return_value = mock_client

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        assert ssh._connect() is False

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_connect_reuses_existing(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        ssh.client = MagicMock()
        assert ssh._connect() is True
        mock_paramiko.SSHClient.assert_not_called()

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_execute_command_success(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_client.exec_command.return_value = (
            MagicMock(),
            mock_stdout,
            mock_stderr,
        )
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh._execute_command("echo hello")
        assert success is True
        assert output == "output"

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_execute_command_nonzero_exit(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"error output"
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_client.exec_command.return_value = (
            MagicMock(),
            mock_stdout,
            mock_stderr,
        )
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh._execute_command("bad_cmd")
        assert success is False
        assert "error output" in output

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_execute_command_exception(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_client.exec_command.side_effect = Exception("channel closed")

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh._execute_command("cmd")
        assert success is False
        assert "channel closed" in output

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_execute_command_connect_fails(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("refused")
        mock_paramiko.SSHClient.return_value = mock_client

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh._execute_command("cmd")
        assert success is False

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_execute_command_transport_inactive(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_client.get_transport.return_value = None

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh._execute_command("cmd")
        assert success is False
        assert "not" in output.lower()

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_resolv_conf_already_exists(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.read.return_value = b"nameserver 8.8.8.8"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_client.exec_command.return_value = (
            MagicMock(),
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, _ = ssh.update_resolv_conf("8.8.8.8")
        assert success is True

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_resolv_conf_adds_new(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            if call_count[0] == 1:
                mock_stdout.read.return_value = b""
                mock_stdout.channel.recv_exit_status.return_value = 1
            else:
                mock_stdout.read.return_value = b"nameserver 8.8.8.8"
                mock_stdout.channel.recv_exit_status.return_value = 0
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, _ = ssh.update_resolv_conf("8.8.8.8")
        assert success is True

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_resolv_conf_write_fails(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"permission denied"
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_client.exec_command.return_value = (
            MagicMock(),
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_resolv_conf("8.8.8.8")
        assert success is False

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_upgrade_success(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            mock_stdout.channel.recv_exit_status.return_value = 0
            if "wget" in cmd:
                mock_stdout.read.return_value = b""
            elif "test -f" in cmd:
                mock_stdout.read.return_value = b"EXISTS"
            elif "foundation_upgrade" in cmd:
                mock_stdout.read.return_value = (
                    b"Successfully completed upgrading foundation"
                )
            elif "genesis stop" in cmd or "genesis restart" in cmd:
                mock_stdout.read.return_value = b""
            else:
                mock_stdout.read.return_value = b""
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        with patch("ztf.helpers.utils.ssh_cvm.time.sleep"):
            success, _ = ssh.update_cvm_foundation(
                "http://example.com/foundation.tar.gz"
            )
        assert success is True

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_download_fails(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"wget failed"
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_client.exec_command.return_value = (
            MagicMock(),
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_cvm_foundation("http://example.com/f.tar.gz")
        assert success is False
        assert "download" in output.lower()

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_file_missing_after_download(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            mock_stdout.channel.recv_exit_status.return_value = 0
            if "wget" in cmd:
                mock_stdout.read.return_value = b""
            elif "test -f" in cmd:
                mock_stdout.read.return_value = b""
                mock_stdout.channel.recv_exit_status.return_value = 1
            else:
                mock_stdout.read.return_value = b""
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_cvm_foundation("http://example.com/f.tar.gz")
        assert success is False
        assert "does not exist" in output

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_upgrade_fails(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            mock_stdout.channel.recv_exit_status.return_value = 0
            if "wget" in cmd:
                mock_stdout.read.return_value = b""
            elif "test -f" in cmd:
                mock_stdout.read.return_value = b"EXISTS"
            elif "foundation_upgrade" in cmd:
                mock_stdout.read.return_value = b"FAILED"
            else:
                mock_stdout.read.return_value = b""
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_cvm_foundation("http://example.com/f.tar.gz")
        assert success is False
        assert "foundation_upgrade failed" in output

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_downgrade_success(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            mock_stdout.channel.recv_exit_status.return_value = 0
            if "test -d" in cmd or "test -f" in cmd:
                mock_stdout.read.return_value = b"EXISTS"
            else:
                mock_stdout.read.return_value = b""
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        with patch("ztf.helpers.utils.ssh_cvm.time.sleep"):
            success, _ = ssh.update_cvm_foundation(
                "http://example.com/f.tar.gz", downgrade=True
            )
        assert success is True

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_downgrade_step_fails(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            if "wget" in cmd or "test -f" in cmd:
                mock_stdout.read.return_value = b"EXISTS" if "test" in cmd else b""
                mock_stdout.channel.recv_exit_status.return_value = 0
            elif "rm -rf ~/foundation" in cmd:
                mock_stdout.read.return_value = b""
                mock_stderr.read.return_value = b"permission denied"
                mock_stdout.channel.recv_exit_status.return_value = 1
            else:
                mock_stdout.read.return_value = b""
                mock_stdout.channel.recv_exit_status.return_value = 0
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_cvm_foundation(
            "http://example.com/f.tar.gz", downgrade=True
        )
        assert success is False

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_downgrade_dir_missing(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            mock_stdout.channel.recv_exit_status.return_value = 0
            if "test -f" in cmd:
                mock_stdout.read.return_value = b"EXISTS"
            elif "test -d" in cmd:
                mock_stdout.read.return_value = b""
                mock_stdout.channel.recv_exit_status.return_value = 1
            else:
                mock_stdout.read.return_value = b""
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_cvm_foundation(
            "http://example.com/f.tar.gz", downgrade=True
        )
        assert success is False
        assert "restored backup" in output

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_genesis_stop_fails(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            if "genesis stop" in cmd:
                mock_stdout.read.return_value = b""
                mock_stderr.read.return_value = b"stop failed"
                mock_stdout.channel.recv_exit_status.return_value = 1
            elif "test -f" in cmd:
                mock_stdout.read.return_value = b"EXISTS"
                mock_stdout.channel.recv_exit_status.return_value = 0
            elif "foundation_upgrade" in cmd:
                mock_stdout.read.return_value = (
                    b"Successfully completed upgrading foundation"
                )
                mock_stdout.channel.recv_exit_status.return_value = 0
            else:
                mock_stdout.read.return_value = b""
                mock_stdout.channel.recv_exit_status.return_value = 0
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        with patch("ztf.helpers.utils.ssh_cvm.time.sleep"):
            success, output = ssh.update_cvm_foundation("http://example.com/f.tar.gz")
        assert success is False
        assert "stop foundation" in output.lower()

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_genesis_restart_fails(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        call_count = [0]

        def exec_side_effect(cmd, timeout=600):
            call_count[0] += 1
            mock_stdout = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read.return_value = b""
            if "genesis restart" in cmd:
                mock_stdout.read.return_value = b""
                mock_stderr.read.return_value = b"restart failed"
                mock_stdout.channel.recv_exit_status.return_value = 1
            elif "test -f" in cmd:
                mock_stdout.read.return_value = b"EXISTS"
                mock_stdout.channel.recv_exit_status.return_value = 0
            elif "foundation_upgrade" in cmd:
                mock_stdout.read.return_value = (
                    b"Successfully completed upgrading foundation"
                )
                mock_stdout.channel.recv_exit_status.return_value = 0
            else:
                mock_stdout.read.return_value = b""
                mock_stdout.channel.recv_exit_status.return_value = 0
            return (MagicMock(), mock_stdout, mock_stderr)

        mock_client.exec_command.side_effect = exec_side_effect

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        with patch("ztf.helpers.utils.ssh_cvm.time.sleep"):
            success, output = ssh.update_cvm_foundation("http://example.com/f.tar.gz")
        assert success is False
        assert "restart genesis" in output.lower()

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_cvm_foundation_exception(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("connection refused")
        mock_paramiko.SSHClient.return_value = mock_client

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_cvm_foundation("http://example.com/f.tar.gz")
        assert success is False

    def test_close_with_no_client(self):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        ssh.close()

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_close_with_client(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        ssh.client = MagicMock()
        ssh.close()
        assert ssh.client is None

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_context_manager(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        with SSHCvm("10.0.0.1", "user", "pass") as ssh:
            assert ssh is not None

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_update_resolv_conf_exception(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("boom")
        mock_paramiko.SSHClient.return_value = mock_client

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_resolv_conf("8.8.8.8")
        assert success is False

    def test_update_resolv_conf_invalid_ip(self):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh.update_resolv_conf("not-an-ip")
        assert success is False
        assert "Invalid" in output

    @patch("ztf.helpers.utils.ssh_cvm.paramiko")
    def test_execute_command_exit_nonzero_no_stderr(self, mock_paramiko):
        from ztf.helpers.utils.ssh_cvm import SSHCvm

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 42
        mock_client.exec_command.return_value = (
            MagicMock(),
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHCvm("10.0.0.1", "user", "pass")
        success, output = ssh._execute_command("false")
        assert success is False
        assert "exit status 42" in output


# ===================================================================
# FC Imaging Helper — uncovered paths
# ===================================================================


class TestFcImagingCoverage:
    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    def _make_helper(self, session):
        from ztf.helpers.fc_imaging import FcImagingHelper

        return FcImagingHelper(session=session)

    def test_get_imaged_nodes_fallback_path(self, mock_session):
        mock_session.post.side_effect = [
            Exception("404"),
            [{"node_serial": "SN1"}],
        ]
        helper = self._make_helper(mock_session)
        result = helper._get_imaged_nodes()
        assert result == [{"node_serial": "SN1"}]

    def test_get_imaged_nodes_entities_key(self, mock_session):
        mock_session.post.return_value = {"entities": [{"node_serial": "SN1"}]}
        helper = self._make_helper(mock_session)
        result = helper._get_imaged_nodes()
        assert result == [{"node_serial": "SN1"}]

    def test_get_imaged_nodes_list_response(self, mock_session):
        mock_session.post.return_value = [{"node_serial": "SN1"}]
        helper = self._make_helper(mock_session)
        result = helper._get_imaged_nodes()
        assert result == [{"node_serial": "SN1"}]

    def test_get_imaged_nodes_empty(self, mock_session):
        mock_session.post.return_value = {}
        helper = self._make_helper(mock_session)
        result = helper._get_imaged_nodes()
        assert result == []

    def test_get_imaged_nodes_error(self, mock_session):
        mock_session.post.side_effect = [
            Exception("fail"),
            Exception("fail"),
        ]
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception):
            helper._get_imaged_nodes()

    def test_create_entity_unavailable_nodes(self, mock_session):
        mock_session.post.return_value = {
            "imaged_nodes": [
                {"node_serial": "SN1", "available": False},
                {"node_serial": "SN2", "available": True},
            ]
        }
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="not available"):
            helper.create_entity(
                {
                    "cluster_name": "test",
                    "nodes_list": [
                        {"node_serial": "SN1"},
                        {"node_serial": "SN2"},
                    ],
                }
            )

    def test_create_entity_no_serials(self, mock_session):
        mock_session.post.return_value = {"imaged_cluster_uuid": "uuid-1"}
        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "cluster_name": "test",
                "nodes_list": [
                    {"cvm_ip": "10.0.0.1"},
                    {"cvm_ip": "10.0.0.2"},
                ],
            }
        )
        assert result == "uuid-1"

    def test_create_entity_all_optional_params(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ]
            },
            {"imaged_cluster_uuid": "uuid-2"},
        ]
        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "cluster_name": "test",
                "nodes_list": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ],
                "imaging_parameters": {
                    "aos_package_url": "http://aos.tar",
                    "aos_package_sha256sum": "abc123",
                    "aos_metadata_url": "http://meta.json",
                },
                "hypervisor_isos": [{"type": "kvm", "url": "http://kvm.iso"}],
                "timezone": "America/Los_Angeles",
                "cvm_vlan_id": 100,
                "cvm_ram_gb": 32,
                "ipmi_gateway": "10.0.0.254",
                "ipmi_netmask": "255.255.255.0",
                "rdma_passthrough": True,
                "enable_lacp": True,
            }
        )
        assert result == "uuid-2"
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["timezone"] == "America/Los_Angeles"
        assert payload["cvm_vlan_id"] == 100
        assert payload["cvm_ram_gb"] == 32
        assert payload["rdma_passthrough"] is True
        assert payload["enable_lacp"] is True

    def test_create_entity_image_and_cluster_mode(self, mock_session):
        mock_session.post.side_effect = [
            {"imaged_nodes": [{"node_serial": "SN1"}]},
            {"imaged_cluster_uuid": "uuid-3"},
        ]
        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "cluster_name": "test",
                "nodes_list": [{"node_serial": "SN1"}],
                "skip_cluster_creation": False,
                "cluster_external_ip": "10.0.0.100",
                "imaging_parameters": {"aos_package_url": "http://aos.tar"},
            }
        )
        assert result == "uuid-3"
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["skip_cluster_creation"] is False
        assert payload["cluster_external_ip"] == "10.0.0.100"

    def test_create_entity_fallback_ext_id(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ]
            },
            {"status": "ok"},
        ]
        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "cluster_name": "my-cluster",
                "nodes_list": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ],
            }
        )
        assert result == "my-cluster"

    def test_list_entities_fallback_path(self, mock_session):
        mock_session.post.side_effect = [
            Exception("404"),
            {
                "imaged_clusters": [
                    {
                        "cluster_name": "c1",
                        "imaged_cluster_uuid": "u1",
                    }
                ]
            },
        ]
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert len(result) == 1

    def test_list_entities_custom_filter(self, mock_session):
        mock_session.post.return_value = {
            "imaged_clusters": [
                {"cluster_name": "c1", "imaged_cluster_uuid": "u1"},
                {"cluster_name": "c2", "imaged_cluster_uuid": "u2"},
            ]
        }
        helper = self._make_helper(mock_session)
        result = helper.list_entities(custom_filter={"cluster_name": "c1"})
        assert len(result) == 1
        assert result[0]["cluster_name"] == "c1"

    def test_list_entities_error(self, mock_session):
        mock_session.post.side_effect = [
            Exception("fail"),
            Exception("fail"),
        ]
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert result == []

    def test_get_entity_fallback_path(self, mock_session):
        mock_session.post.side_effect = [
            Exception("404"),
            {
                "imaged_clusters": [
                    {
                        "cluster_name": "c1",
                        "imaged_cluster_uuid": "u1",
                    }
                ]
            },
        ]
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("u1")
        assert result is not None

    def test_get_entity_error(self, mock_session):
        mock_session.post.side_effect = [
            Exception("fail"),
            Exception("fail"),
        ]
        helper = self._make_helper(mock_session)
        result = helper.get_entity_by_ext_id("u1")
        assert result is None

    def test_create_entity_sanitizes_node_records(self, mock_session):
        """IPMI fields stripped and invalid node_role corrected."""
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {
                        "node_serial": "SN1",
                        "ipmi_ip": "10.49.46.141",
                        "ipmi_gateway": "10.49.46.129",
                        "ipmi_netmask": "255.255.255.128",
                        "node_role": "unsupported_node",
                        "cvm_ip": "10.48.28.101",
                    },
                    {
                        "node_serial": "SN2",
                        "ipmi_ip": "10.49.47.37",
                        "ipmi_gateway": "10.49.47.1",
                        "ipmi_netmask": "255.255.255.128",
                        "node_role": "unsupported_node",
                        "cvm_ip": "10.48.28.107",
                    },
                    {
                        "node_serial": "SN3",
                        "ipmi_ip": "10.49.47.11",
                        "ipmi_gateway": "10.49.47.1",
                        "ipmi_netmask": "255.255.255.128",
                        "node_role": "hyperconverged",
                        "cvm_ip": "10.48.28.137",
                    },
                ]
            },
            {"imaged_cluster_uuid": "uuid-mixed"},
        ]
        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "cluster_name": "mixed-ipmi",
                "nodes_list": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                    {"node_serial": "SN3"},
                ],
            }
        )
        assert result == "uuid-mixed"
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert "redundancy_factor" not in payload
        assert payload["cluster_name"] == "mixed-ipmi"
        nodes = payload["nodes_list"]
        for n in nodes:
            assert "ipmi_ip" not in n
            assert "ipmi_gateway" not in n
            assert "ipmi_netmask" not in n
            assert "node_serial" in n
            assert n["node_role"] == "hyperconverged"


# ===================================================================
# FC Cluster Helper — uncovered paths
# ===================================================================


class TestFcClusterCoverage:
    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    def _make_helper(self, session):
        from ztf.helpers.fc_cluster import FcClusterHelper

        return FcClusterHelper(session=session)

    def test_get_imaged_nodes_fallback(self, mock_session):
        mock_session.post.side_effect = [
            Exception("404"),
            [{"node_serial": "SN1"}],
        ]
        helper = self._make_helper(mock_session)
        result = helper._get_imaged_nodes()
        assert result == [{"node_serial": "SN1"}]

    def test_get_imaged_nodes_entities_key(self, mock_session):
        mock_session.post.return_value = {"entities": [{"node_serial": "SN1"}]}
        helper = self._make_helper(mock_session)
        result = helper._get_imaged_nodes()
        assert result == [{"node_serial": "SN1"}]

    def test_get_imaged_nodes_list_response(self, mock_session):
        mock_session.post.return_value = [{"node_serial": "SN1"}]
        helper = self._make_helper(mock_session)
        assert helper._get_imaged_nodes() == [{"node_serial": "SN1"}]

    def test_get_imaged_nodes_empty(self, mock_session):
        mock_session.post.return_value = {}
        helper = self._make_helper(mock_session)
        assert helper._get_imaged_nodes() == []

    def test_get_imaged_nodes_error(self, mock_session):
        mock_session.post.side_effect = [Exception("x"), Exception("x")]
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception):
            helper._get_imaged_nodes()

    def test_create_entity_unavailable(self, mock_session):
        mock_session.post.return_value = {
            "imaged_nodes": [
                {"node_serial": "SN1", "available": False},
                {"node_serial": "SN2"},
            ]
        }
        helper = self._make_helper(mock_session)
        with pytest.raises(ValueError, match="not available"):
            helper.create_entity(
                {
                    "cluster_name": "c1",
                    "nodes_list": [
                        {"node_serial": "SN1"},
                        {"node_serial": "SN2"},
                    ],
                }
            )

    def test_create_entity_all_optional_params(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ]
            },
            {"imaged_cluster_uuid": "uuid-c"},
        ]
        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "cluster_name": "c1",
                "nodes_list": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ],
                "timezone": "UTC",
                "cvm_vlan_id": 200,
                "cvm_ram_gb": 64,
                "rdma_passthrough": False,
                "enable_lacp": True,
            }
        )
        assert result == "uuid-c"
        payload = mock_session.post.call_args_list[1][1]["data"]
        assert payload["cvm_vlan_id"] == 200
        assert payload["cvm_ram_gb"] == 64
        assert payload["rdma_passthrough"] is False
        assert payload["enable_lacp"] is True

    def test_create_entity_fallback_ext_id(self, mock_session):
        mock_session.post.side_effect = [
            {
                "imaged_nodes": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ]
            },
            {"status": "ok"},
        ]
        helper = self._make_helper(mock_session)
        result = helper.create_entity(
            {
                "cluster_name": "my-c",
                "nodes_list": [
                    {"node_serial": "SN1"},
                    {"node_serial": "SN2"},
                ],
            }
        )
        assert result == "my-c"

    def test_list_entities_fallback(self, mock_session):
        mock_session.post.side_effect = [
            Exception("404"),
            {
                "imaged_clusters": [
                    {
                        "cluster_name": "c",
                        "imaged_cluster_uuid": "u",
                    }
                ]
            },
        ]
        helper = self._make_helper(mock_session)
        result = helper.list_entities()
        assert len(result) == 1

    def test_get_entity_error(self, mock_session):
        mock_session.post.side_effect = [Exception("x"), Exception("x")]
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("u1") is None


# ===================================================================
# GenerateFcApiKeyHelper — uncovered paths
# ===================================================================


class TestGenerateFcApiKeyCoverage:
    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    def _make_helper(self, session):
        from ztf.helpers.generate_fc_api_key import GenerateFcApiKeyHelper

        return GenerateFcApiKeyHelper(session=session)

    def test_is_fc_enabled_false(self, mock_session):
        mock_session.get.return_value = {"isFoundationCentralEnabled": False}
        helper = self._make_helper(mock_session)
        assert helper._is_fc_enabled() is False

    def test_list_api_keys_fallback(self, mock_session):
        mock_session.post.side_effect = [
            Exception("404"),
            {"api_keys": [{"alias": "k1"}]},
        ]
        helper = self._make_helper(mock_session)
        result = helper._list_api_keys()
        assert result == [{"alias": "k1"}]

    def test_list_api_keys_double_error(self, mock_session):
        mock_session.post.side_effect = [Exception("x"), Exception("x")]
        helper = self._make_helper(mock_session)
        with pytest.raises(Exception):
            helper._list_api_keys()

    def test_list_api_keys_entities_key(self, mock_session):
        mock_session.post.return_value = {"entities": [{"alias": "k2"}]}
        helper = self._make_helper(mock_session)
        result = helper._list_api_keys()
        assert result == [{"alias": "k2"}]

    def test_list_api_keys_list_response(self, mock_session):
        mock_session.post.return_value = [{"alias": "k3"}]
        helper = self._make_helper(mock_session)
        result = helper._list_api_keys()
        assert result == [{"alias": "k3"}]

    def test_list_api_keys_empty(self, mock_session):
        mock_session.post.return_value = {}
        helper = self._make_helper(mock_session)
        assert helper._list_api_keys() == []

    def test_list_entities_error(self, mock_session):
        mock_session.post.side_effect = [Exception("x"), Exception("x")]
        helper = self._make_helper(mock_session)
        assert helper.list_entities() == []

    def test_get_entity_error(self, mock_session):
        mock_session.post.side_effect = [Exception("x"), Exception("x")]
        helper = self._make_helper(mock_session)
        assert helper.get_entity_by_ext_id("k1") is None
