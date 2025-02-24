import pytest
from framework.helpers.exception_utils import RestError, ResponseError, JsonError, YamlError


class TestRestError:
    def test_rest_error_default_message(self):
        e = RestError()
        assert str(e) == "An error occurred with REST API call."
        assert e.error == 'RestError'

    def test_rest_error_custom_message(self):
        message = "Custom REST error message."
        e = RestError(message=message)
        assert str(e) == message
        assert e.error == 'RestError'

    def test_rest_error_custom_error(self):
        error = "CustomError"
        e = RestError(error=error)
        assert e.error == error

    def test_rest_error_additional_attributes(self):
        e = RestError(foo="bar", baz=123)
        assert e.foo == "bar"
        assert e.baz == 123

class TestResponseError:
    def test_response_error_default_message(self):
        e = ResponseError()
        assert str(e) == "An error occurred with REST API response."
        assert e.error == 'ResponseError'

    def test_response_error_custom_message(self):
        message = "Custom Response error message."
        e = ResponseError(message=message)
        assert str(e) == message
        assert e.error == 'ResponseError'

    def test_response_error_custom_error(self):
        error = "CustomError"
        e = ResponseError(error=error)
        assert e.error == error

    def test_response_error_additional_attributes(self):
        e = ResponseError(foo="bar", baz=123)
        assert e.foo == "bar"
        assert e.baz == 123

class TestJsonError:
    def test_json_error_default_message(self):
        e = JsonError()
        assert str(e) == "Something went wrong while parsing json file!"
        assert e.error == 'JSON-parse-error'

    def test_json_error_custom_message(self):
        message = "Custom JSON error message."
        e = JsonError(message=message)
        assert str(e) == message
        assert e.error == 'JSON-parse-error'

    def test_json_error_custom_error(self):
        error = "CustomError"
        e = JsonError(error=error)
        assert e.error == error

    def test_json_error_additional_attributes(self):
        e = JsonError(foo="bar", baz=123)
        assert e.foo == "bar"
        assert e.baz == 123

class TestYamlError:
    def test_yaml_error_default_message(self):
        e = YamlError()
        assert str(e) == "Something went wrong while parsing yml file!"
        assert e.error == 'YAML-parse-error'

    def test_yaml_error_custom_message(self):
        message = "Custom YAML error message."
        e = YamlError(message=message)
        assert str(e) == message
        assert e.error == 'YAML-parse-error'

    def test_yaml_error_custom_error(self):
        error = "CustomError"
        e = YamlError(error=error)
        assert e.error == error

    def test_yaml_error_additional_attributes(self):
        e = YamlError(foo="bar", baz=123)
        assert e.foo == "bar"
        assert e.baz == 123