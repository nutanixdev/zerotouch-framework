import copy
from base64 import b64encode
from typing import Union, List, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from framework.helpers.rest_utils import RestAPIUtil
from framework.helpers.general_utils import intersection
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class Entity:
    entities_limitation = 20
    entity_type = "entities"
    port = "9440"

    def __init__(
        self,
        ip=None,
        username=None,
        password=None,
        resource_type=None,
        session=None,
        headers=None,
        scheme="https"
    ):
        self.build_spec_methods = {}
        secured = True if scheme == "https" else False
        self.session = session if session else RestAPIUtil(
            ip, user=username, pwd=password, port=self.port, headers=headers, secured=secured)
        self.resource = resource_type

    def get_response(self, uri: str, method="GET", **kwargs):
        if method == "GET":
            return self.session.get(uri, **kwargs)
        elif method == "POST":
            return self.session.post(uri, **kwargs)
        elif method == "PUT":
            return self.session.put(uri, **kwargs)
        elif method == "PATCH":
            return self.session.patch(uri, **kwargs)
        elif method == "DELETE":
            return self.session.delete(uri, **kwargs)
        else:
            raise "Invalid method"

    def read(
        self,
        uuid=None,
        method="GET",
        data=None,
        headers=None,
        endpoint=None,
        query=None,
        timeout=None,
        entity_type=None,
        custom_filters=None
    ):
        uri = self.resource + "/{0}".format(uuid) if uuid else self.resource
        if endpoint:
            uri = uri + "/{0}".format(endpoint)
        if query:
            uri = self._build_url_with_query(uri, query)

        if method == "GET":
            if timeout:
                resp = self.get_response(uri, timeout=timeout, headers=headers)
            else:
                resp = self.get_response(uri, headers=headers)
        elif method == "POST":
            if timeout:
                resp = self.get_response(uri, method="POST", data=data, headers=headers, timeout=timeout)
            else:
                resp = self.get_response(uri, method="POST", data=data, headers=headers)
        else:
            raise "Invalid method"

        entity_type = entity_type if entity_type else self.entity_type
        if custom_filters:
            entities_list = self._filter_entities(resp[entity_type], custom_filters)
            resp = entities_list

        if entity_type in resp:
            resp = resp[entity_type]
        return resp

    def create(
        self,
        data=None,
        endpoint=None,
        query=None,
        jsonify=True,
        timeout=None,
        files=None
    ):
        uri = self.resource + "/{0}".format(endpoint) if endpoint else self.resource
        if query:
            uri = self._build_url_with_query(uri, query)
        if timeout:
            resp = self.get_response(uri, method="POST", data=data, jsonify=jsonify, timeout=timeout, files=files)
        else:
            resp = self.get_response(uri, method="POST", data=data, jsonify=jsonify, files=files)

        return resp

    def update(
        self,
        data=None,
        endpoint=None,
        query=None,
        timeout=None,
        method="PUT"
    ):
        uri = self.resource + "/{0}".format(endpoint) if endpoint else self.resource
        if query:
            uri = self._build_url_with_query(uri, query)
        if method == "PUT":
            if timeout:
                resp = self.get_response(uri, method="PUT", data=data, timeout=timeout)
            else:
                resp = self.get_response(uri, method="PUT", data=data)
        elif method == "PATCH":
            if timeout:
                resp = self.get_response(uri, method="PATCH", data=data, timeout=timeout)
            else:
                resp = self.get_response(uri, method="PATCH", data=data)
        else:
            raise "Invalid method"
        return resp

    def list(
        self,
        endpoint=None,
        use_base_url=False,
        query=None,
        data=None,
        custom_filters=None,
        timeout=None,
        entity_type=None
    ) -> Union[List, Dict]:
        uri = self.resource if use_base_url else self.resource + "/list"
        if endpoint:
            uri = uri + "/{0}".format(endpoint)
        if query:
            uri = self._build_url_with_query(uri, query)

        if timeout:
            resp = self.get_response(uri, method="POST", data=data, timeout=timeout)
        else:
            resp = self.get_response(uri, method="POST", data=data)

        entity_type = entity_type if entity_type else self.entity_type
        if custom_filters:
            entities_list = self._filter_entities(resp[entity_type], custom_filters)
            resp = entities_list

        if entity_type in resp:
            resp = resp[entity_type]
        return resp

    def upload_json(
        self,
        data=None,
        headers=None,
        endpoint=None,
        query=None,
        timeout=None,
        jsonify=None,
        files=None
    ):
        uri = self.resource + "/{0}".format(endpoint) if endpoint else self.resource
        if query:
            uri = self._build_url_with_query(uri, query)
        if timeout:
            resp = self.get_response(uri, method="POST", headers=headers, jsonify=jsonify, data=data, timeout=timeout,
                                     files=files)
        else:
            resp = self.get_response(uri, method="POST", headers=headers, jsonify=jsonify, data=data, files=files)

        return resp

    def upload(
        self,
        source,
        data,
        endpoint="import_file",
        query=None,
        timeout=30,
    ):
        uri = self.resource + "/{0}".format(endpoint) if endpoint else self.resource
        if query:
            uri = self._build_url_with_query(uri, query)
        return self._upload_file(
            uri,
            source,
            data,
            timeout=timeout,
        )

    def delete(
        self,
        uuid=None,
        timeout=None,
        endpoint=None,
        query=None,
    ):
        uri = self.resource + "/{0}".format(uuid) if uuid else self.resource
        if endpoint:
            uri = uri + "/{0}".format(endpoint)
        if query:
            uri = self._build_url_with_query(uri, query)
        try:
            if timeout:
                resp = self.get_response(uri, method="DELETE", timeout=timeout)
            else:
                resp = self.get_response(uri, method="DELETE")
        except Exception as e:
            raise e

        return resp

    def get_spec(self, params: Optional[Dict] = None, spec: Optional[dict] = None) -> (Optional[Dict], Optional[str]):
        params = params if params else {}
        spec = spec or self._get_default_spec()

        for param, config in params.items():
            build_spec_method = self.build_spec_methods.get(param)
            if build_spec_method and config:
                spec, error = build_spec_method(spec, config, copy.deepcopy(params))
                if error:
                    return None, error
        return spec, None

    @staticmethod
    def _build_url_with_query(url, query):
        """
        Query will a dictionary of query parameters
        """
        url = urlparse(url)
        query_ = dict(parse_qsl(url.query))
        query_.update(query)
        query_ = urlencode(query_)
        url = url._replace(query=query_)
        return urlunparse(url)

    @staticmethod
    def _filter_entities(entities, custom_filters):
        filtered_entities = []
        for entity in entities:
            if intersection(entity, copy.deepcopy(custom_filters)):
                filtered_entities.append(entity)
        return filtered_entities

    # upload file in chunks to the given url
    def _upload_file(self, uri, source, data, timeout=120):
        headers = {
            'Accept': 'application/json'
        }
        kwargs = {
            "data": data,
            "headers": headers,
            "files": {'file': ('blob', open(source, 'rb'), 'application/json')},
            "jsonify": False
        }
        if timeout:
            kwargs["timeout"] = timeout
        response = self.get_response(uri, method="POST", **kwargs)
        return response

    # todo make this abstractmethod in future
    @staticmethod
    def _get_default_spec():
        pass
