class RestError(Exception):
    """A REST error occurred."""

    def __init__(self, message=None, error=None, **kwargs):
        self.message = (
            "An error occurred with REST API call." if message is None else message
        )
        super().__init__(self.message)
        self.error = "RestError" if error is None else error
        for attr in kwargs:
            setattr(self, attr, kwargs[attr])


class ResponseError(Exception):
    """A Response error occurred."""

    def __init__(self, message=None, error=None, **kwargs):
        self.message = (
            "An error occurred with REST API response." if message is None else message
        )
        super().__init__(self.message)
        self.error = "ResponseError" if error is None else error
        for attr in kwargs:
            setattr(self, attr, kwargs[attr])
