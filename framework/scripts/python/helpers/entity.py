import copy
from base64 import b64encode
from typing import Union, List, Dict
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
        self.build_spec_methods = None
        secured = True if scheme == "https" else False
        self.session = session if session else RestAPIUtil(
            ip, user=username, pwd=password, port=self.port, headers=headers, secured=secured)
        self.resource = resource_type

    def read(
        self,
        uuid=None,
        method="GET",
        data=None,
        endpoint=None,
        query=None,
        timeout=None,
    ):
        uri = self.resource + "/{0}".format(uuid) if uuid else self.resource
        if endpoint:
            uri = uri + "/{0}".format(endpoint)
        if query:
            uri = self._build_url_with_query(uri, query)

        if method == "GET":
            if timeout:
                resp = self.session.get(uri, timeout=timeout)
            else:
                resp = self.session.get(uri)
        elif method == "POST":
            if timeout:
                resp = self.session.post(uri, data=data, timeout=timeout)
            else:
                resp = self.session.post(uri, data=data)
        else:
            raise "Invalid method"

        if self.entity_type in resp:
            resp = resp[self.entity_type]
        return resp

    def create(
        self,
        data=None,
        endpoint=None,
        query=None,
        jsonify=True,
        timeout=None
    ):
        uri = self.resource + "/{0}".format(endpoint) if endpoint else self.resource
        if query:
            uri = self._build_url_with_query(uri, query)
        if timeout:
            resp = self.session.post(
                uri,
                data=data,
                jsonify=jsonify,
                timeout=timeout
            )
        else:
            resp = self.session.post(
                uri,
                data=data,
                jsonify=jsonify
            )

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
                resp = self.session.put(uri, data=data, timeout=timeout)
            else:
                resp = self.session.put(uri, data=data)
        elif method == "PATCH":
            if timeout:
                resp = self.session.patch(uri, data=data, timeout=timeout)
            else:
                resp = self.session.patch(uri, data=data)
        else:
            raise "Invalid method"
        return resp

    def list(
        self,
        endpoint=None,
        use_base_url=False,
        data=None,
        custom_filters=None,
        timeout=None,
        entity_type=None
    ) -> Union[List, Dict]:
        uri = self.resource if use_base_url else self.resource + "/list"
        if endpoint:
            uri = uri + "/{0}".format(endpoint)

        if timeout:
            resp = self.session.post(uri, data=data, timeout=timeout)
        else:
            resp = self.session.post(uri, data=data)

        entity_type = entity_type if entity_type else self.entity_type
        if custom_filters:
            entities_list = self._filter_entities(resp[entity_type], custom_filters)
            resp = entities_list

        if entity_type in resp:
            resp = resp[entity_type]
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
        timeout=None,
        endpoint=None,
        query=None,
    ):
        uri = self.resource + "/{0}".format(endpoint) if endpoint else self.resource
        if query:
            uri = self._build_url_with_query(uri, query)
        try:
            if timeout:
                resp = self.session.delete(uri, timeout=timeout)
            else:
                resp = self.session.delete(uri)
        except Exception as e:
            raise e

        return resp

    def get_spec(self, old_spec=None, params=None):
        spec = copy.deepcopy(old_spec) or self._get_default_spec()
        for param, config in params.items():
            build_spec_method = self.build_spec_methods.get(param)
            if build_spec_method and config:
                spec, error = build_spec_method(spec, config)
                if error:
                    return None, error
        return spec, None

    @staticmethod
    def _build_headers(module, additional_headers):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if additional_headers:
            headers.update(additional_headers)
        usr = module.params.get("nutanix_username")
        pas = module.params.get("nutanix_password")
        if usr and pas:
            cred = "{0}:{1}".format(usr, pas)
            try:
                encoded_cred = b64encode(bytes(cred, encoding="ascii")).decode("ascii")
            except BaseException:
                encoded_cred = b64encode(bytes(cred).encode("ascii")).decode("ascii")
            auth_header = "Basic " + encoded_cred
            headers.update({"Authorization": auth_header})
        return headers

    @staticmethod
    def _build_url_with_query(url, query):
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
        response = self.session.post(uri=uri, **kwargs)
        return response

    @staticmethod
    def _get_default_spec():
        pass
