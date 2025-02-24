from unittest.mock import patch, MagicMock
import pytest
import requests
import responses 
import requests_mock
import json

from unittest.mock import patch, MagicMock
from framework.helpers.rest_utils import RestAPIUtil, rest_api_call
from framework.helpers.exception_utils import RestError, ResponseError
from tests.unit.config.test_data import *

class TestRestAPICallDecorator:
    """
    Test class for the rest_api_call decorator.
    """
    
    @pytest.mark.parametrize(
        "status_code, expected_error",
        [
            (401, "Unauthorized. Please check your credentials."),
            (404, "{'code': 404,"),
            (500, "{'code': 500,"),
        ],
    )
    def test_rest_api_call_decorator_error(self, status_code, expected_error):
        #Note : Add all the possible exceptions that can occur in the RestAPIUtil class.
        #If the Exception is not handled in the decorator, the Script will fail without any error message.
        @rest_api_call
        def mock_func(url):
            response = requests.get(url)
            return response

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://example.com", status=status_code, body="Unauthorized" if status_code == 401 else "")
            with pytest.raises(RestError) as excinfo:
                mock_func("http://example.com")
            assert expected_error in str(excinfo.value)

    @pytest.mark.parametrize(
        "status_code, response_body",
        [
            (401, b"<Response [401]>"),
            (502, b"<Response [502]>"),
        ],
    )
    def test_rest_api_call_specific_response(self, status_code, response_body):
        @rest_api_call
        def mock_func(url):
            response = MagicMock()
            response.status_code = status_code
            response.content = response_body
            return response

        with pytest.raises(ResponseError) as excinfo:
            mock_func("http://example.com")
        assert f"{status_code}" in str(excinfo.value)

    def test_rest_api_call_success_json(self):
        @rest_api_call
        def mock_func(url):
            response = requests.get(url)
            return response

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://example.com", json={"data": "success"}, status=200)
            response = mock_func("http://example.com")
            assert response == {"data": "success"}

    def test_rest_api_call_success_text(self):
        @rest_api_call
        def mock_func(url):
            response = requests.get(url)
            return response

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://example.com", body='{"result": "success"}', status=200, content_type='text/plain')
            response = mock_func("http://example.com")
            assert response == {'result': 'success'}
            
    def test_rest_api_call_success_empty_json(self):
        @rest_api_call
        def mock_func(url):
            response = requests.get(url)
            return response

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://example.com", json={}, status=200)
            response = mock_func("http://example.com")
            assert response == {}

    def test_rest_api_call_success_empty_text(self):
        @rest_api_call
        def mock_func(url):
            response = requests.get(url)
            return response

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://example.com", body='', status=200)
            response = mock_func("http://example.com")
            assert response == {}


# Define your exceptions and corresponding expected error messages
exceptions_check = {
    requests.exceptions.HTTPError("HTTPError occured"): 'HTTPError',
    requests.exceptions.ConnectionError("ConnectionError occured"): 'ConnectionError',
    requests.exceptions.Timeout("Timeout Error occured"): 'Timeout Error',
    requests.exceptions.RequestException("Request Exception occured"): 'Request Exception',
    Exception("UnexpectedError occured"): 'UnexpectedError'
}



class TestRestAPIUtil:
    """
    Test class for the RestAPIUtil class.
    """
    
    @pytest.fixture()
    def rest_util_obj(self):
        return RestAPIUtil(**REST_ARGS)


    def raise_exceptions(self, rest_util_obj, req_type: str):
        if req_type == "get":
            obj = getattr(rest_util_obj, 'get')
        elif req_type == "post":
            obj = getattr(rest_util_obj, 'post')
        else:
            return
        for exception, error in EXCEPTIONS_CHECK.items():
            with pytest.raises(RestError) as e:
                obj(REST_URI)
                assert e.value.error == error

    @patch('requests.Session.get', side_effect=exceptions_check.keys())
    def test_exceptions_get(self, _, rest_util_obj):
        self.raise_exceptions(rest_util_obj, "get")

    @patch('requests.Session.post', side_effect=exceptions_check.keys())
    def test_exceptions_post(self, _, rest_util_obj):
        self.raise_exceptions(rest_util_obj, "post")


    def test_response_get_text(self):
        with requests_mock.Mocker() as request_mocker:
            request_mocker.get(f"https://1.1.1.1:9440/{REST_URI}", text='resp')
            rest_util_obj = RestAPIUtil(**REST_ARGS)
            assert rest_util_obj.get(REST_URI) == 'resp'


    def test_response_get_text_unauthorized(self):
        with requests_mock.Mocker() as request_mocker:
            request_mocker.get(f"https://1.1.1.1:9440/{REST_URI}", text='<Response [401]>')
            rest_util_obj = RestAPIUtil(**REST_ARGS)
            with pytest.raises(ResponseError):
                rest_util_obj.get(REST_URI)



    def test_response_get_text_bad_gateway(self):
        with requests_mock.Mocker() as request_mocker:
            request_mocker.get(f"https://1.1.1.1:9440/{REST_URI}", text='<Response [502]>')
            rest_util_obj = RestAPIUtil(**REST_ARGS)
            with pytest.raises(ResponseError):
                rest_util_obj.get(REST_URI)


    def test_response_get_json(self):
        with requests_mock.Mocker() as request_mocker:
            request_mocker.get(f"https://1.1.1.1:9440/{REST_URI}", json=GET_RESPONSE, status_code=200,
                            headers=API_HEADERS)
            rest_util_obj = RestAPIUtil(**REST_ARGS)
            assert rest_util_obj.get(REST_URI) == GET_RESPONSE


    def test_response_post_json(self):
        with requests_mock.Mocker() as request_mocker:
            request_mocker.post(f"https://1.1.1.1:9440/{REST_URI}", json=POST_RESPONSE, status_code=200,
                                headers=API_HEADERS)
            rest_util_obj = RestAPIUtil(**REST_ARGS)
            assert rest_util_obj.post(REST_URI) == POST_RESPONSE

    def test_response_patch_json(self):
        with requests_mock.Mocker() as request_mocker:
            request_mocker.patch(f"https://1.1.1.1:9440/{REST_URI}", json=PATCH_RESPONSE, status_code=200,
                                headers=API_HEADERS)
            rest_util_obj = RestAPIUtil(**REST_ARGS)
            assert rest_util_obj.patch(REST_URI) == PATCH_RESPONSE

    def test_response_delete(self):
        with requests_mock.Mocker() as request_mocker:
            request_mocker.delete(f"https://1.1.1.1:9440/{REST_URI}", status_code=200,
                                headers=API_HEADERS)
            rest_util_obj = RestAPIUtil(**REST_ARGS)
            response = rest_util_obj.delete(REST_URI)
            assert response.status_code == 200
    
    def test_response_delete_error(self):
        
        mock_response = {
            "state": "ERROR",
            "code": 401,
            "message_list": [
                {
                    "reason": "AUTHENTICATION_REQUIRED",
                    "message": "Authentication required.",
                    "details": "Basic realm=\"Intent Gateway Login Required\""
                }
            ],
            "api_version": "3.1"
        }
        
        with requests_mock.Mocker() as request_mocker:
            request_mocker.delete(f"https://1.1.1.1:9440/{REST_URI}", status_code=401,
                                headers=API_HEADERS,
                                json=mock_response
                            )
            rest_util_obj = RestAPIUtil(**REST_ARGS)
            with pytest.raises(RestError) as e:
                rest_util_obj.delete(REST_URI)
            assert e.value.error == 'HTTPError'