class RestError(Exception):
    """A REST error occurred."""

    def __init__(self, message=None, error=None, **kwargs):
        self.message = "An error occurred with REST API call." \
            if message is None else message
        super(RestError, self).__init__(self.message)
        self.error = 'RestError' if error is None else error
        try:
            for attr in kwargs:
                setattr(self, attr, kwargs[attr])
        except:
            pass


class ResponseError(Exception):
    """A Response error occurred."""

    def __init__(self, message=None, error=None, **kwargs):
        self.message = "An error occurred with REST API response." \
            if message is None else message
        super(ResponseError, self).__init__(self.message)
        self.error = 'ResponseError' if error is None else error
        try:
            for attr in kwargs:
                setattr(self, attr, kwargs[attr])
        except:
            pass


class JsonError(Exception):
    """Exception occurred while parsing Yaml"""

    def __init__(self, message=None, error=None, **kwargs):
        self.message = "Something went wrong while parsing json file!" \
            if message is None else message
        super(JsonError, self).__init__(self.message)
        self.error = 'JSON-parse-error' if error is None else error
        try:
            for attr in kwargs:
                setattr(self, attr, kwargs[attr])
        except:
            pass


class YamlError(Exception):
    """Exception occurred while parsing Yaml"""

    def __init__(self, message=None, error=None, **kwargs):
        self.message = "Something went wrong while parsing yml file!" \
            if message is None else message
        super(YamlError, self).__init__(self.message)
        self.error = 'YAML-parse-error' if error is None else error
        try:
            for attr in kwargs:
                setattr(self, attr, kwargs[attr])
        except:
            pass
