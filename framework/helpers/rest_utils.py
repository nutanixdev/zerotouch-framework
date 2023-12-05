import json
import requests
import urllib3
from .log_utils import get_logger
from requests.exceptions import Timeout, ConnectionError, HTTPError, RequestException
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from typing import Optional
from .exception_utils import RestError, ResponseError

logger = get_logger(__name__)
pool_maxsize = 20
pool_connections = 20
pool_block = True


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        super(TimeoutHTTPAdapter, self).__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        if not kwargs.get("timeout"):
            kwargs["timeout"] = (3, 150)
        return super().send(request, **kwargs)


def rest_api_call(func):
    """
    Decorator function to handle API calls and exceptions

    Args:
        func: The function that is making the call
    :param func:
    :return:
    """

    def make_call(*args, **kwargs):
        r = None
        try:
            r = func(*args, **kwargs)
            if r.headers.get('Content-Type') == 'application/json':
                response = r.json()
            else:
                response = r.content
                response = response.decode("utf-8")
                # Sometimes json response is sent back as a string
                try:
                    response = json.loads(response)
                except Exception:
                    logger.debug("Cannot parse string response to json")

            logger.debug(response)
            r.raise_for_status()
        except HTTPError as errh:
            status_code = r.status_code if hasattr(r, "status_code") else 500

            if status_code == "401":
                err_msg = "Unauthorized. Please check your credentials."
            elif hasattr(r, "json") and callable(getattr(r, "json")):
                try:
                    err_msg = r.json()
                except Exception:
                    err_msg = errh
            elif hasattr(r, "text"):
                err_msg = r.text
            else:
                err_msg = errh

            logger.error(err_msg)
            raise RestError(message=str(err_msg), error="HTTPError")
        except ConnectionError as errc:
            raise RestError(message=str(errc), error="ConnectionError")
        except Timeout as errt:
            raise RestError(message=str(errt), error="Timeout Error")
        except RequestException as err:
            raise RestError(message=str(err), error="Request Exception")
        except KeyboardInterrupt:
            raise KeyboardInterrupt()
        except Exception as e:
            raise RestError(message=str(e), error="UnexpectedError")

        if str(response) == '<Response [401]>':
            raise ResponseError(message=str(response), error="LoginFailed")
        elif str(response) == '<Response [502]>':
            raise ResponseError(message=str(response), error="BadGateway")
        return response

    return make_call


class RestAPIUtil:
    def __init__(self, ip_address: str, user: Optional[str], pwd: Optional[str], headers: dict = None,
                 secured: bool = True, port: str = ""):
        self.__IP_ADDRESS = ip_address
        self.__SSL_ENABLED = bool(secured)
        self.__PORT = f":{port}" if port else port
        self.__session = requests.Session()
        self.__headers = headers if headers else {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if user and pwd:
            self.__session.auth = HTTPBasicAuth(user, pwd)

        # Define the retry strategy
        retry_strategy = Retry(
            total=3,  # Maximum number of retries (including the initial request)
            backoff_factor=1.5,  # Backoff factor between retries, keeping it to 1.5 seconds
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry
            method_whitelist=[
                    "GET",
                    "PUT",
                    "DELETE",
                    "POST",
                ]
        )

        # Create an HTTP adapter with the retry strategy
        # TODO: add pool connections, pool_maxsize to HTTP ADAPTER
        http_adapter = TimeoutHTTPAdapter(
                # timeout=(3, 150),
                max_retries=retry_strategy,
                pool_block=pool_block,
                pool_connections=pool_connections,
                pool_maxsize=pool_maxsize,
            )
        # Mount the HTTP adapter to the session
        self.__session.mount("http://", http_adapter)
        self.__session.mount("https://", http_adapter)

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @rest_api_call
    def post(self, uri: str, headers: dict = None, data: dict = None, jsonify=True, **kwargs):
        headers = headers if headers else self.__headers
        data = {} if not data else data
        url = self.prepare_url(uri)

        logger.debug("POST request for the URL: " + url)
        data = json.dumps(data) if jsonify else data

        logger.debug(data)
        response = self.__session.post(url, headers=headers, data=data, verify=False, **kwargs)
        return response

    @rest_api_call
    def put(self, uri: str, headers: dict = None, data: dict = None, jsonify=True, **kwargs):
        headers = headers if headers else self.__headers
        data = {} if not data else data
        url = self.prepare_url(uri)

        logger.debug("PUT request for the URL: " + url)
        data = json.dumps(data) if jsonify else data

        if data:
            logger.debug(data)
        response = self.__session.put(url, headers=headers, data=data, verify=False, **kwargs)
        return response

    @rest_api_call
    def get(self, uri: str, headers: dict = None, data: dict = None, **kwargs):
        headers = headers if headers else self.__headers
        data = {} if not data else data
        url = self.prepare_url(uri)
        headers = {} if not headers else headers

        logger.debug("GET request for the URL: " + url)
        if data:
            logger.debug(data)
            response = self.__session.get(url, headers=headers, data=json.dumps(data), verify=False, **kwargs)
        else:
            response = self.__session.get(url, headers=headers, verify=False, **kwargs)
        return response

    def prepare_url(self, uri):
        return f"{self.get_protocol()}://{self.__IP_ADDRESS}{self.__PORT}/{uri}"

    def get_protocol(self):
        if self.__SSL_ENABLED <= 0:
            return 'http'
        return 'https'
