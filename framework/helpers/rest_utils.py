import json
import traceback
import requests
import requests_cache
import urllib3
from .log_utils import get_logger
from requests.exceptions import Timeout, ConnectionError, HTTPError, RequestException
from requests.packages.urllib3.util.retry import Retry
from requests.exceptions import ConnectTimeout
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
            kwargs["timeout"] = (5, 60)
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
                try:
                    response = r.json()
                except Exception as e:
                    # In Case of No or Empty Data .json() gives Exception

                    # Added this logic to avoid
                    if str(r) in ['<Response [200]>', '<Response [204]>']:
                        response = r
                    else:
                        raise e
            else:
                response = r.content
                response = response.decode("utf-8")
                # Sometimes json response is sent back as a string
                try:
                    response = json.loads(response)
                except Exception:
                    logger.debug("Cannot parse string response to json")

            logger.debug(f"RESPONSE: {response}")
            r.raise_for_status()
        # except ConnectionError as e:
        #     error = {"err_msg": e}
        #     raise RestError(message=str(error), error="ConnectionError")
        except Exception as err:
            logger.debug("Got traceback\n{}".format(traceback.format_exc()))

            status_code = r.status_code if hasattr(r, "status_code") else 500
            error = {"code": status_code}

            if str(status_code).startswith("5") or str(status_code).startswith("4"):
                if r:
                    error["response"] = r

            if status_code == "401":
                err_msg = "Unauthorized. Please check your credentials."
            elif hasattr(r, "json") and callable(getattr(r, "json")):
                try:
                    err_msg = r.json()
                except Exception:
                    err_msg = f"{err}"
            elif hasattr(r, "text"):
                err_msg = r.text
            else:
                err_msg = f"{err}"

            error["error"] = err_msg
            raise RestError(message=str(error), error="HTTPError")

        if str(response) == '<Response [401]>':
            raise ResponseError(message=str(response), error="LoginFailed")
        elif str(response) == '<Response [502]>':
            raise ResponseError(message=str(response), error="BadGateway")
        return response

    return make_call


class RestAPIUtil:
    def __init__(self, ip_address: str, user: Optional[str], pwd: Optional[str], headers: dict = None,
                 secured: bool = True, port: str = "", cache: bool = False):
        self.__IP_ADDRESS = ip_address
        self.__SSL_ENABLED = bool(secured)
        self.__PORT = f":{port}" if port else port
        self.__session = requests.Session() if not cache else requests_cache.CachedSession(
            expire_after=60,
            backend='sqlite',
            allowable_methods=('GET',),
        )
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
            ],
            raise_on_status=False,
        )

        # Create an HTTP adapter with the retry strategy
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
    def post(self, uri: str, headers: dict = None, data: dict = None, jsonify=True, verify=False, **kwargs):
        headers = headers if headers else self.__headers
        data = {} if not data else data
        url = self.prepare_url(uri)

        logger.debug("POST request for the URL: " + url)
        data = json.dumps(data) if jsonify else data

        if data:
            logger.debug(f"POST payload: {data}")
        response = self.__session.post(url, headers=headers, data=data, verify=verify, **kwargs)
        return response

    @rest_api_call
    def put(self, uri: str, headers: dict = None, data: dict = None, jsonify=True, verify=False, **kwargs):
        headers = headers if headers else self.__headers
        data = {} if not data else data
        url = self.prepare_url(uri)

        logger.debug("PUT request for the URL: " + url)
        data = json.dumps(data) if jsonify else data

        if data:
            logger.debug(f"PUT payload: {data}")
        response = self.__session.put(url, headers=headers, data=data, verify=verify, **kwargs)
        return response

    @rest_api_call
    def get(self, uri: str, headers: dict = None, data: dict = None, verify=False, **kwargs):
        headers = headers if headers else self.__headers
        data = {} if not data else data
        url = self.prepare_url(uri)
        headers = {} if not headers else headers

        logger.debug("GET request for the URL: " + url)
        if data:
            logger.debug(f"GET payload: {data}")
            response = self.__session.get(url, headers=headers, data=json.dumps(data), verify=False, **kwargs)
        else:
            response = self.__session.get(url, headers=headers, verify=verify, **kwargs)
        return response

    @rest_api_call
    def delete(self, uri: str, headers: dict = None, verify=False, **kwargs):
        headers = headers if headers else self.__headers
        url = self.prepare_url(uri)
        headers = {} if not headers else headers

        logger.debug("DELETE request for the URL: " + url)
        response = self.__session.delete(url, headers=headers, verify=verify, **kwargs)
        return response

    @rest_api_call
    def patch(self, uri: str, headers: dict = None, data: dict = None, jsonify=True, verify=False, **kwargs):
        headers = headers if headers else self.__headers
        data = {} if not data else data
        url = self.prepare_url(uri)

        logger.debug("PATCH request for the URL: " + url)
        data = json.dumps(data) if jsonify else data

        if data:
            logger.debug(f"PATCH payload: {data}")
        response = self.__session.patch(url, headers=headers, data=data, verify=verify, **kwargs)
        return response

    def prepare_url(self, uri):
        return f"{self.get_protocol()}://{self.__IP_ADDRESS}{self.__PORT}/{uri}"

    def get_protocol(self):
        if self.__SSL_ENABLED <= 0:
            return 'http'
        return 'https'
