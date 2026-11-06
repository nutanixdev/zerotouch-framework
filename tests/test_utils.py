import json
import logging
import os

import pytest
import yaml

from ztf.utils.utils import (
    get_logger,
    raise_api_exception,
    read_input_file,
    redact_secrets,
    strip_internal_attributes,
    strip_internal_attributes_for_an_entity,
    write_output_file,
)


class DummyError(Exception):
    def __init__(self, message=None, status=None, reason=None, body=None):
        self.message = message
        self.status = status
        self.reason = reason
        self.body = body


def test_raise_api_exception_with_message_status_reason():
    exc = DummyError(message="msg", status=404, reason="Not Found", body=None)
    result = raise_api_exception(exc)
    assert result["msg"] == "msg"
    assert result["status"] == 404
    assert result["error"] == "Not Found"
    assert "response" in result


def test_raise_api_exception_with_json_body():
    body = json.dumps({"data": {"error": {"foo": "bar"}}})
    exc = DummyError(body=body)
    result = raise_api_exception(exc)
    assert result["msg"] == {"foo": "bar"}


def test_raise_api_exception_with_json_body_no_error():
    body = json.dumps({"foo": "bar"})
    exc = DummyError(body=body)
    result = raise_api_exception(exc)
    assert "response" in result


def test_raise_api_exception_with_invalid_json_body():
    exc = DummyError(body="not a json")
    result = raise_api_exception(exc)
    assert "response" in result


def test_raise_api_exception_with_error_in_response():
    exc = DummyError(body=json.dumps({"error": {"foo": "bar"}}))
    result = raise_api_exception(exc)
    assert "response" in result


def test_raise_api_exception_with_no_body():
    exc = DummyError()
    result = raise_api_exception(exc)
    assert "response" in result


def test_strip_internal_attributes_removes_keys():
    data = {
        "_object_type": "foo",
        "$objectType": "top.level.Model",
        "keep": "bar",
        "nested": {"$objectType": "nested.OneOf.Variant", "keep2": "val"},
    }
    result = strip_internal_attributes(data)
    assert "_object_type" not in result
    assert "$objectType" not in result  # stripped at top level
    assert (
        "$objectType" in result["nested"]
    )  # preserved at nested level (OneOf discriminator)
    assert result["keep"] == "bar"
    assert result["nested"]["keep2"] == "val"


def test_strip_internal_attributes_with_list():
    data = [
        {"_object_type": "foo", "keep": "bar"},
        {"$objectType": "baz", "keep2": "val"},
    ]
    result = strip_internal_attributes(data)
    # When called on a top-level list, each element is at depth >= 1,
    # so $objectType is preserved (OneOf discriminator).
    assert "_object_type" not in result[0]
    assert "$objectType" in result[1]


def test_strip_internal_attributes_preserves_nested_discriminator():
    """$objectType is stripped at depth 0 but preserved at deeper levels."""
    data = {
        "$objectType": "monitoring.v4.serviceability.UdaPolicy",
        "title": "cpu-alert",
        "triggerConditions": [
            {
                "$objectType": "monitoring.v4.serviceability.TriggerCondition",
                "condition": {
                    "$objectType": "monitoring.v4.serviceability.Condition",
                    "thresholdValue": {
                        "$objectType": "monitoring.v4.common.IntValue",
                        "intValue": 100,
                    },
                },
            }
        ],
    }
    result = strip_internal_attributes(data)
    assert "$objectType" not in result  # root stripped
    tc = result["triggerConditions"][0]
    assert tc["$objectType"] == "monitoring.v4.serviceability.TriggerCondition"
    assert tc["condition"]["$objectType"] == "monitoring.v4.serviceability.Condition"
    assert (
        tc["condition"]["thresholdValue"]["$objectType"]
        == "monitoring.v4.common.IntValue"
    )


def test_strip_internal_attributes_with_exclude():
    data = {"_object_type": "foo", "keep": "bar"}
    result = strip_internal_attributes(data, exclude_attributes=["_object_type"])
    assert "_object_type" in result


def test_get_logger_returns_logger():
    logger = get_logger("test_logger")
    assert hasattr(logger, "info")
    # Should not add duplicate handlers
    logger2 = get_logger("test_logger")
    assert logger is logger2


def test_get_logger_respects_existing_file_handler(tmp_path):
    logger_name = "test_logger_file_handler"
    logger = logging.getLogger(logger_name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    file_handler = logging.FileHandler(tmp_path / "log.txt")
    logger.addHandler(file_handler)
    try:
        returned = get_logger(logger_name)
        assert returned is logger
        assert (
            sum(isinstance(handler, logging.FileHandler) for handler in logger.handlers)
            == 1
        )
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


def test_read_input_file_json(tmp_path):
    data = {"foo": "bar"}
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(data, f)
    result = read_input_file(str(file_path))
    assert result == data


def test_read_input_file_yaml(tmp_path):
    data = {"foo": "bar"}
    file_path = tmp_path / "test.yaml"
    with open(file_path, "w") as f:
        yaml.safe_dump(data, f)
    result = read_input_file(str(file_path))
    assert result == data


def test_read_input_file_yml(tmp_path):
    data = {"foo": "bar"}
    file_path = tmp_path / "test.yml"
    with open(file_path, "w") as f:
        yaml.safe_dump(data, f)
    result = read_input_file(str(file_path))
    assert result == data


def test_read_input_file_unsupported(tmp_path):
    file_path = tmp_path / "test.txt"
    with open(file_path, "w") as f:
        f.write("foo")
    with pytest.raises(ValueError):
        read_input_file(str(file_path))


def test_write_output_file_json(tmp_path):
    data = {"foo": "bar"}
    file_path = tmp_path / "out.json"
    write_output_file(str(file_path), data)
    with open(file_path) as f:
        loaded = json.load(f)
    assert loaded == data


def test_write_output_file_yaml(tmp_path):
    data = {"foo": "bar"}
    file_path = tmp_path / "out.yaml"
    write_output_file(str(file_path), data)
    with open(file_path) as f:
        loaded = yaml.safe_load(f)
    assert loaded == data


def test_write_output_file_yml(tmp_path):
    data = {"foo": "bar"}
    file_path = tmp_path / "out.yml"
    write_output_file(str(file_path), data)
    with open(file_path) as f:
        loaded = yaml.safe_load(f)
    assert loaded == data


def test_write_output_file_unsupported(tmp_path):
    file_path = tmp_path / "out.txt"
    with pytest.raises(ValueError):
        write_output_file(str(file_path), {"foo": "bar"})


# Tests for strip_internal_attributes_for_an_entity function


def test_strip_internal_attributes_for_an_entity_category():
    """Test strip_internal_attributes_for_an_entity with 'category' entity."""
    data = {
        "type": "category_type",
        "name": "test_category",
        "description": "test description",
        "_object_type": "category",
    }
    result = strip_internal_attributes_for_an_entity(data, "category")

    # Should remove both global internal attributes and entity-specific attributes
    assert "type" not in result  # entity-specific attribute
    assert "_object_type" not in result  # global internal attribute
    assert "name" in result  # should be preserved
    assert "description" in result  # should be preserved


def test_strip_internal_attributes_for_an_entity_category_with_exclude():
    """Test strip_internal_attributes_for_an_entity with exclude_attributes."""
    data = {
        "type": "category_type",
        "name": "test_category",
        "_object_type": "category",
    }
    result = strip_internal_attributes_for_an_entity(
        data, "category", exclude_attributes=["type"]
    )

    # Should preserve "type" due to exclude_attributes
    assert "type" in result  # excluded from stripping
    assert "_object_type" not in result  # global internal attribute still removed
    assert "name" in result  # should be preserved


def test_strip_internal_attributes_for_an_entity_unknown_entity():
    """Test strip_internal_attributes_for_an_entity with unknown entity name.

    Unknown entity names do not raise; they use only global internal
    attributes for stripping.
    """
    data = {
        "name": "test_entity",
        "_object_type": "unknown",
    }
    result = strip_internal_attributes_for_an_entity(data, "unknown_entity")
    assert "_object_type" not in result
    assert result["name"] == "test_entity"


def test_strip_internal_attributes_for_an_entity_nested_data():
    """Test strip_internal_attributes_for_an_entity with nested data structures."""
    data = {
        "type": "category_type",
        "name": "test_category",
        "nested": {
            "type": "nested_type",
            "value": "nested_value",
            "_object_type": "nested",
        },
        "list_data": [
            {"type": "list_item_type", "item": "list_item", "$objectType": "list_item"}
        ],
    }
    result = strip_internal_attributes_for_an_entity(data, "category")

    # Top level
    assert "type" not in result  # entity-specific attribute
    assert "name" in result  # should be preserved

    # Nested dict - only global internal attributes are stripped recursively
    assert (
        "type" in result["nested"]
    )  # entity-specific attribute NOT stripped from nested
    assert "_object_type" not in result["nested"]  # global internal attribute stripped
    assert "value" in result["nested"]  # should be preserved

    # List items - $objectType preserved at nested level (OneOf discriminator)
    assert (
        "type" in result["list_data"][0]
    )  # entity-specific attribute NOT stripped from nested
    assert "$objectType" in result["list_data"][0]  # preserved at nested level
    assert "item" in result["list_data"][0]  # should be preserved


def test_strip_internal_attributes_for_an_entity_empty_data():
    """Test strip_internal_attributes_for_an_entity with empty data."""
    data = {}
    result = strip_internal_attributes_for_an_entity(data, "category")
    assert result == {}


def test_strip_internal_attributes_for_an_entity_list_data():
    """Test strip_internal_attributes_for_an_entity with list data."""
    data = [
        {"type": "category_type_1", "name": "category_1", "_object_type": "category"},
        {"type": "category_type_2", "name": "category_2", "$objectType": "category"},
    ]
    result = strip_internal_attributes_for_an_entity(data, "category")

    # Entity-specific attributes are only stripped from top level, not from list items
    assert (
        "type" in result[0] and "type" in result[1]
    )  # entity-specific attribute NOT stripped from list items
    assert "_object_type" not in result[0]  # _object_type stripped (always internal)
    assert (
        "$objectType" in result[1]
    )  # $objectType preserved at nested level (OneOf discriminator)
    assert "name" in result[0] and "name" in result[1]


def test_strip_internal_attributes_for_an_entity_none_exclude_attributes():
    """Test strip_internal_attributes_for_an_entity with None exclude_attributes."""
    data = {
        "type": "category_type",
        "name": "test_category",
        "_object_type": "category",
    }
    result = strip_internal_attributes_for_an_entity(
        data, "category", exclude_attributes=None
    )

    # Should behave the same as default (empty list)
    assert "type" not in result
    assert "_object_type" not in result
    assert "name" in result


def test_strip_internal_attributes_for_an_entity_empty_exclude_attributes():
    """Test strip_internal_attributes_for_an_entity with empty exclude_attributes."""
    data = {
        "type": "category_type",
        "name": "test_category",
        "_object_type": "category",
    }
    result = strip_internal_attributes_for_an_entity(
        data, "category", exclude_attributes=[]
    )

    # Should behave the same as default
    assert "type" not in result
    assert "_object_type" not in result
    assert "name" in result


def test_strip_internal_attributes_for_an_entity_multiple_exclude_attributes():
    """Test strip_internal_attributes_for_an_entity with multiple exclude_attributes."""
    data = {
        "type": "category_type",
        "name": "test_category",
        "_object_type": "category",
        "createdTime": "2023-01-01",
    }
    result = strip_internal_attributes_for_an_entity(
        data, "category", exclude_attributes=["type", "createdTime"]
    )

    # Should preserve both excluded attributes
    assert "type" in result  # excluded
    assert "createdTime" in result  # excluded
    assert "_object_type" not in result  # not excluded, so removed
    assert "name" in result  # should be preserved


# ---------------------------------------------------------------------------
# snake_to_camel tests
# ---------------------------------------------------------------------------

from ztf.utils.utils import snake_to_camel  # noqa: E402


def test_snake_to_camel_dict():
    result = snake_to_camel({"my_key": "val", "other_key": 1})
    assert result == {"myKey": "val", "otherKey": 1}


def test_snake_to_camel_list():
    result = snake_to_camel([{"my_key": "val"}])
    assert result == [{"myKey": "val"}]


def test_snake_to_camel_nested():
    result = snake_to_camel({"outer_key": {"inner_key": "val"}})
    assert result == {"outerKey": {"innerKey": "val"}}


def test_snake_to_camel_no_underscore():
    result = snake_to_camel({"name": "x"})
    assert result == {"name": "x"}


def test_snake_to_camel_primitive():
    assert snake_to_camel("hello") == "hello"
    assert snake_to_camel(42) == 42


# ---------------------------------------------------------------------------
# raise_api_exception edge cases
# ---------------------------------------------------------------------------


def test_raise_api_exception_with_explicit_msg():
    exc = DummyError()
    result = raise_api_exception(exc, msg="custom message")
    assert result["msg"] == "custom message"


def test_raise_api_exception_json_decode_error_with_error_key():
    """Non-JSON body that contains 'error' as a dict."""
    body_str = "not valid json"
    exc = DummyError(body=body_str)
    result = raise_api_exception(exc)
    assert "response" in result


def test_raise_api_exception_bytes_body_is_decoded():
    """SDK exceptions may carry bytes bodies; they must not crash."""
    body = json.dumps({"data": {"error": {"code": "E42"}}}).encode("utf-8")
    exc = DummyError(body=body)
    result = raise_api_exception(exc)
    assert result["msg"] == {"code": "E42"}


def test_raise_api_exception_bytes_body_invalid_json_is_decoded():
    """Bytes body that is not JSON is returned verbatim (utf-8 decoded)."""
    exc = DummyError(body=b"plain text error")
    result = raise_api_exception(exc)
    assert result["response"] == "plain text error"


def test_raise_api_exception_body_with_non_dict_data_section():
    """``data`` is not a dict — must not raise AttributeError."""
    body = json.dumps({"data": "surprise string", "meta": 1})
    exc = DummyError(body=body)
    result = raise_api_exception(exc)
    assert "response" in result
    assert "msg" not in result


def test_raise_api_exception_body_is_bare_list():
    """Top-level JSON array bodies fall through to ``response``."""
    body = json.dumps([{"foo": 1}, {"bar": 2}])
    exc = DummyError(body=body)
    result = raise_api_exception(exc)
    assert result["response"] == [{"foo": 1}, {"bar": 2}]


def test_raise_api_exception_plain_string_body_with_error_substring_does_not_crash():
    """Previous implementation raised TypeError on this path (regression)."""
    exc = DummyError(body="unexpected error: timed out")
    result = raise_api_exception(exc)
    assert result["response"] == "unexpected error: timed out"


def test_raise_api_exception_status_preserved_across_body_paths():
    body = json.dumps({"data": {"error": {"reason": "BadRequest"}}})
    exc = DummyError(status=400, reason="Bad Request", body=body)
    result = raise_api_exception(exc)
    assert result["status"] == 400
    assert result["error"] == "Bad Request"
    assert result["msg"] == {"reason": "BadRequest"}


def test_raise_api_exception_dict_body_passes_through():
    """Some SDK paths hand us an already-parsed dict in .body."""
    exc = DummyError(body={"data": {"error": {"code": "E11"}}})
    result = raise_api_exception(exc)
    assert result["msg"] == {"code": "E11"}


# ---------------------------------------------------------------------------
# get_logger edge cases
# ---------------------------------------------------------------------------


def test_get_logger_with_log_file(tmp_path):
    log_file = str(tmp_path / "test.log")
    logger = get_logger("test_log_file_logger", log_file=log_file)
    assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)


def test_get_logger_makedirs(tmp_path):
    log_file = str(tmp_path / "subdir" / "nested" / "test.log")
    get_logger("test_makedirs_logger", log_file=log_file)
    assert os.path.exists(os.path.dirname(log_file))


def test_get_logger_file_exception(monkeypatch):
    """When file logging fails, logger still returned."""
    monkeypatch.setattr("os.path.exists", lambda p: False)
    monkeypatch.setattr(
        "os.makedirs", lambda p, **kw: (_ for _ in ()).throw(OSError("fail"))
    )
    logger = get_logger("test_fail_logger", log_file="/invalid/path/log.txt")
    assert logger is not None


# ---------------------------------------------------------------------------
# redact_secrets
# ---------------------------------------------------------------------------


class TestRedactSecrets:
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "Password",
            "serviceAccountPassword",
            "smtpPassword",
            "clientSecret",
            "api_secret",
            "accessToken",
            "refreshToken",
            "passphrase",
            "privateKey",
            "apiKey",
            "authPassword",
            "privPassword",
            "credential",
            "user_credential",
        ],
    )
    def test_masks_sensitive_keys(self, key: str) -> None:
        redacted = redact_secrets({key: "topsecret"})
        assert redacted[key] == "***"

    def test_preserves_non_sensitive_values(self) -> None:
        data = {"name": "admin", "enabled": True, "count": 0, "host": "1.2.3.4"}
        assert redact_secrets(data) == data

    def test_walks_nested_dicts(self) -> None:
        data = {
            "user": {"name": "admin", "password": "p"},
            "list": [{"token": "t"}, {"safe": "v"}],
        }
        out = redact_secrets(data)
        assert out["user"]["password"] == "***"
        assert out["user"]["name"] == "admin"
        assert out["list"][0]["token"] == "***"
        assert out["list"][1]["safe"] == "v"

    def test_does_not_mutate_input(self) -> None:
        data = {"password": "p", "nested": {"token": "t"}}
        redact_secrets(data)
        assert data == {"password": "p", "nested": {"token": "t"}}

    def test_preserves_none_value(self) -> None:
        assert redact_secrets({"password": None}) == {"password": None}

    def test_depth_guard(self) -> None:
        # Build a deeply nested dict beyond the 32-depth guard.
        deep: object = "leaf"
        for _ in range(40):
            deep = {"child": deep}
        out = redact_secrets(deep)
        # No RecursionError; guard message returned at the bottom.
        assert out is not None

    def test_non_dict_non_list_returned_verbatim(self) -> None:
        assert redact_secrets("plain") == "plain"
        assert redact_secrets(42) == 42
        assert redact_secrets(None) is None
