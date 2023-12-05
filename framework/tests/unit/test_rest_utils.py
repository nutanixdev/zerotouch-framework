import pytest
import requests_mock
from unittest import mock
from framework.helpers.rest_utils import *
from .test_data import REST_ARGS, REST_URI, GET_RESPONSE, POST_RESPONSE, API_HEADERS


@pytest.fixture()
def rest_util_obj():
    return RestAPIUtil(**REST_ARGS)


def raise_exceptions(rest_util_obj, req_type: str):
    if req_type == "get":
        obj = getattr(rest_util_obj, 'get')
    elif req_type == "post":
        obj = getattr(rest_util_obj, 'post')
    else:
        return
    with pytest.raises(RestError) as e:
        obj(REST_URI)
    assert e.value.error == 'HTTPError'
    with pytest.raises(RestError) as e:
        obj(REST_URI)
    assert e.value.error == 'ConnectionError'
    with pytest.raises(RestError) as e:
        obj(REST_URI)
    assert e.value.error == 'Timeout Error'
    with pytest.raises(RestError) as e:
        obj(REST_URI)
    assert e.value.error == 'Request Exception'
    with pytest.raises(RestError) as e:
        obj(REST_URI)
    assert e.value.error == 'UnexpectedError'


@mock.patch('requests.Session.get', side_effect=[requests.exceptions.HTTPError('whoops'),
                                                 requests.exceptions.ConnectionError('Aich'),
                                                 requests.exceptions.Timeout('Oops'),
                                                 requests.exceptions.RequestException("Hehe"),
                                                 Exception("Ayyo")])
def test_exceptions_get(_, rest_util_obj):
    raise_exceptions(rest_util_obj, "get")


@mock.patch('requests.Session.post', side_effect=[requests.exceptions.HTTPError('whoops'),
                                                  requests.exceptions.ConnectionError('Aich'),
                                                  requests.exceptions.Timeout('Oops'),
                                                  requests.exceptions.RequestException("Hehe"),
                                                  Exception("Ayyo")])
def test_exceptions_post(_, rest_util_obj):
    raise_exceptions(rest_util_obj, "post")


def test_response_get_text():
    with requests_mock.Mocker() as request_mocker:
        request_mocker.get(f"https://1.1.1.1:9440/{REST_URI}", text='resp')
        rest_util_obj = RestAPIUtil(**REST_ARGS)
        assert rest_util_obj.get(REST_URI) == 'resp'


def test_response_get_text_unauthorized():
    with requests_mock.Mocker() as request_mocker:
        request_mocker.get(f"https://1.1.1.1:9440/{REST_URI}", text='<Response [401]>')
        rest_util_obj = RestAPIUtil(**REST_ARGS)
        with pytest.raises(ResponseError):
            rest_util_obj.get(REST_URI)


def test_response_get_text_bad_gateway():
    with requests_mock.Mocker() as request_mocker:
        request_mocker.get(f"https://1.1.1.1:9440/{REST_URI}", text='<Response [502]>')
        rest_util_obj = RestAPIUtil(**REST_ARGS)
        with pytest.raises(ResponseError):
            rest_util_obj.get(REST_URI)


def test_response_get_json():
    with requests_mock.Mocker() as request_mocker:
        request_mocker.get(f"https://1.1.1.1:9440/{REST_URI}", json=GET_RESPONSE, status_code=200,
                           headers=API_HEADERS)
        rest_util_obj = RestAPIUtil(**REST_ARGS)
        assert rest_util_obj.get(REST_URI) == GET_RESPONSE


def test_response_post_json():
    with requests_mock.Mocker() as request_mocker:
        request_mocker.post(f"https://1.1.1.1:9440/{REST_URI}", json=POST_RESPONSE, status_code=200,
                            headers=API_HEADERS)
        rest_util_obj = RestAPIUtil(**REST_ARGS)
        assert rest_util_obj.post(REST_URI) == POST_RESPONSE
