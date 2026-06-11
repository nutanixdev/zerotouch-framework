import json
import logging
import os
import sys
import tempfile
import time
from typing import Any

import json5
import yaml

stream_logger_format = "%(asctime)s %(levelname)s [%(filename)s:%(lineno)s] %(message)s"

file_logger_format = (
    "%(asctime)s %(levelname)s [%(threadName)s:%(name)s:%(lineno)d] %(message)s"
)


class LocalTimeFormatter(logging.Formatter):
    """Formatter that uses local time and the ZTF format string.

    Nutanix SDK loggers ship with a ``%(asctime)sZ`` format and
    ``converter = time.gmtime``.  Replacing the SDK handler's formatter
    with this class normalizes all timestamps to local time without a
    trailing ``Z``.
    """

    def __init__(
        self, fmt: str = stream_logger_format, *args: object, **kwargs: object
    ):
        super().__init__(fmt, *args, **kwargs)  # type: ignore[arg-type]
        self.converter = time.localtime


class ColoredFormatter(LocalTimeFormatter):
    """Stream formatter that applies ANSI colors based on log level.

    Colors are only applied when the output stream is a TTY.  Piped or
    redirected output remains plain text.

    Args:
        fmt: Log format string (defaults to ``stream_logger_format``).
        stream: The output stream to check for TTY (defaults to stderr).
    """

    _LEVEL_COLORS: dict[int, str] = {
        logging.DEBUG: "\033[36m",  # cyan
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    _RESET = "\033[0m"

    def __init__(
        self,
        fmt: str = stream_logger_format,
        *args: object,
        stream: Any = None,
        **kwargs: object,
    ):
        super().__init__(fmt, *args, **kwargs)
        target = stream or sys.stderr
        self._use_color: bool = hasattr(target, "isatty") and target.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format *record* with ANSI color when outputting to a TTY."""
        formatted = super().format(record)
        if not self._use_color:
            return formatted
        color = self._LEVEL_COLORS.get(record.levelno, "")
        if color:
            return f"{color}{formatted}{self._RESET}"
        return formatted


def snake_to_camel(data: Any) -> Any:
    """
    Recursively convert all snake_case keys to camelCase in dictionaries.

    :param data: Input data (dict, list, or primitive)
    :return: Data with all snake_case keys converted to camelCase
    """

    def convert_key(key: str) -> str:
        """Convert a single snake_case key to camelCase."""
        if not isinstance(key, str) or "_" not in key:
            return key

        # Split by underscore and capitalize each word except the first
        components = key.split("_")
        return components[0] + "".join(word.capitalize() for word in components[1:])

    if isinstance(data, dict):
        return {convert_key(key): snake_to_camel(value) for key, value in data.items()}
    if isinstance(data, list):
        return [snake_to_camel(item) for item in data]
    return data


def raise_api_exception(exception: Any, msg: str | None = None) -> dict[str, Any]:
    """Extract structured error context from an SDK API exception.

    The Nutanix SDK raises a mix of ``ApiException`` shapes across the
    17 supported namespaces: some carry a JSON-encoded ``body`` with
    ``{"data": {"error": {...}}}``, some carry a JSON dict at the top
    level, some carry a plain-text body, and some carry ``bytes``.  This
    helper normalises all of them into a single kwargs dict that the
    caller can forward to ``Exception(...)`` or log verbatim.

    Args:
        exception: The exception raised by the SDK (duck-typed; only
            ``message``, ``status``, ``reason`` and ``body`` attributes
            are consulted).
        msg: Optional override for the primary ``msg`` field.

    Returns:
        A dict with any subset of the keys ``msg``, ``status``,
        ``error`` and ``response``.  Exactly one of ``msg`` / ``response``
        is always present so callers can format a single human-readable
        message without branching.
    """
    kwargs: dict[str, Any] = {}
    if msg:
        kwargs["msg"] = msg
    if message := getattr(exception, "message", None):
        kwargs["msg"] = message
    if status := getattr(exception, "status", None):
        kwargs["status"] = status
    if error := getattr(exception, "reason", None):
        kwargs["error"] = error

    body = getattr(exception, "body", None)
    if not body:
        kwargs["response"] = str(exception)
        return kwargs

    # Try to parse *body* as JSON.  Non-string bodies (``bytes``) are
    # decoded; anything else is stringified.  Regardless of type, a
    # parse failure falls back to the raw body and never raises.
    if isinstance(body, (str, bytes, bytearray)):
        try:
            parsed_body: Any = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            kwargs["response"] = (
                body.decode("utf-8", errors="replace")
                if isinstance(body, (bytes, bytearray))
                else body
            )
            return kwargs
    else:
        parsed_body = body

    # Prefer the standard Nutanix shape ``{"data": {"error": {...}}}``
    # so the error object ends up in ``msg``.  Fall back to dumping the
    # whole parsed body under ``response``.
    if isinstance(parsed_body, dict):
        data_section = parsed_body.get("data")
        api_error = (
            data_section.get("error") if isinstance(data_section, dict) else None
        )
        if api_error:
            kwargs["msg"] = strip_internal_attributes(api_error)
        else:
            kwargs["response"] = strip_internal_attributes(parsed_body)
    else:
        kwargs["response"] = parsed_body

    return kwargs


_SENSITIVE_KEY_SUBSTRINGS: tuple[str, ...] = (
    "password",
    "secret",
    "token",
    "passphrase",
    "privatekey",
    "apikey",
    "authpassword",
    "privpassword",
    "credential",
)


def redact_secrets(data: Any, _depth: int = 0) -> Any:
    """Return a copy of *data* with sensitive values masked.

    Recursively walks dicts and lists.  Any string-typed key whose
    lowercase form contains a known sensitive substring (``password``,
    ``secret``, ``token``, ``passphrase``, ``privatekey``, ``apikey``,
    ``authpassword``, ``privpassword``, ``credential``) has its value
    replaced with ``"***"``; ``None`` values are preserved so absence is
    still visible in logs.  Non-sensitive values are kept verbatim.

    Intended for DEBUG logging of request / response bodies that may
    contain credentials (e.g. ``directoryService.serviceAccountPassword``,
    ``snmpUser.authPassword``, ``smtpServer.password``).

    Args:
        data: Dict, list, or any JSON-serialisable value.
        _depth: Internal recursion depth guard (callers should omit).

    Returns:
        A redacted copy.  The input is not mutated.
    """
    if _depth > 32:
        return "<redact_secrets: max depth exceeded>"
    if isinstance(data, dict):
        redacted: dict[Any, Any] = {}
        for key, value in data.items():
            if isinstance(key, str) and any(
                token in key.lower() for token in _SENSITIVE_KEY_SUBSTRINGS
            ):
                redacted[key] = "***" if value is not None else None
            else:
                redacted[key] = redact_secrets(value, _depth + 1)
        return redacted
    if isinstance(data, list):
        return [redact_secrets(item, _depth + 1) for item in data]
    return data


def strip_internal_attributes(
    data: Any,
    exclude_attributes: list[str] | None = None,
    custom_internal_attributes: list[str] | None = None,
    _depth: int = 0,
) -> Any:
    """Strip SDK-internal / read-only keys from a serialised entity dict.

    ``$objectType`` is only stripped at the **top level** (depth 0).  Nested
    occurrences are preserved because they act as required discriminators for
    OneOf / polymorphic API fields (e.g. ``thresholdValue`` in UDA policies).

    Args:
        data: Serialised entity dict (mutated in-place).
        exclude_attributes: Keys to never strip regardless of depth.
        custom_internal_attributes: Extra keys to strip (all depths).
        _depth: Recursion depth (callers should not set this).

    Returns:
        The same ``data`` reference, stripped in-place.
    """
    always_strip = [
        "_object_type",
        "_reserved",
        "_unknown_fields",
        "$dataItemDiscriminator",
        "$reserved",
        "$unknownFields",
        "createdTime",
        "lastUpdatedTime",
        "createdBy",
        "links",
        "ownerUuid",
    ]

    # $objectType at the root is SDK model metadata (e.g.
    # "monitoring.v4.serviceability.UdaPolicy").  At nested levels it is a
    # required OneOf discriminator and must be kept.
    if _depth == 0:
        always_strip.append("$objectType")

    custom_internal_attributes = custom_internal_attributes or []
    internal_attributes = always_strip + custom_internal_attributes

    if exclude_attributes is None:
        exclude_attributes = []

    if isinstance(data, dict):
        for attr in internal_attributes:
            if attr in data and attr not in exclude_attributes:
                data.pop(attr)
        for val in data.values():
            if isinstance(val, dict):
                strip_internal_attributes(val, exclude_attributes, _depth=_depth + 1)
            elif isinstance(val, list) and val and isinstance(val[0], dict):
                for item in val:
                    strip_internal_attributes(
                        item, exclude_attributes, _depth=_depth + 1
                    )
    elif isinstance(data, list):
        for item in data:
            strip_internal_attributes(item, exclude_attributes, _depth=_depth + 1)
    return data


def strip_internal_attributes_for_an_entity(
    data: Any, entity_name: str, exclude_attributes=None
):
    """
    Strip internal attributes from the data of a specific entity.

    :param data: The data to process.
    :param entity_name: The name of the entity.
    :param exclude_attributes: List of attributes to exclude from stripping.
    :return: Processed data with internal attributes and entity attributes stripped
    """
    entity_internal_attributes = {
        "category": ["type"],
    }
    return strip_internal_attributes(
        data, exclude_attributes, entity_internal_attributes.get(entity_name)
    )


def get_logger(name: str, log_file: str | None = None) -> logging.Logger:
    """Return a named logger with stream and (optionally) file handlers.

    The stream handler defaults to INFO so the console stays clean.
    ``configure_root_logger`` in ``main.py`` promotes it to DEBUG when
    the ``--debug`` CLI flag is used.  The root file handler (also set up
    by ``configure_root_logger``) always captures DEBUG — including
    tracebacks logged with ``exc_info=True``.

    Args:
        name: Logger name (typically ``__name__``).
        log_file: Optional path for a per-module file handler.

    Returns:
        Configured logger.
    """
    logger = logging.getLogger(name)
    if any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        return logger

    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setLevel(logging.INFO)
    logger_stream_handler.setFormatter(
        ColoredFormatter(stream=logger_stream_handler.stream)
    )
    logger.addHandler(logger_stream_handler)

    if any(isinstance(handler, logging.FileHandler) for handler in logger.handlers):
        return logger
    # Add file handler for persistent logs
    try:
        if log_file is None:
            default_log = os.path.join(tempfile.gettempdir(), "ztf.log")
            log_file = os.environ.get("ZTF_LOG_FILE", default_log)
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(LocalTimeFormatter(fmt=file_logger_format))
        logger.addHandler(file_handler)
    except Exception as exc:
        # File logging is best-effort; continue with stream handler only
        logging.getLogger(__name__).debug("File logging setup failed: %s", exc)
    return logger


def read_input_file(filename: str):
    extension = os.path.splitext(filename)[1].lstrip(".")
    with open(filename, encoding="utf-8") as f:
        if extension == "json":
            return json5.load(f)
        if extension in {"yml", "yaml"}:
            return yaml.safe_load(f)
        raise ValueError(f"Unsupported file extension: {extension}")


def write_output_file(filename: str, data: Any) -> None:
    """
    Write data to an output file based on the file extension.

    :param filename: The name of the file to write to.
    :param data: The data to write to the file.
    """
    extension = os.path.splitext(filename)[1].lstrip(".")
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        if extension == "json":
            json.dump(data, f, indent=2)
        elif extension in {"yml", "yaml"}:
            yaml.safe_dump(data, f, sort_keys=False)
        else:
            raise ValueError(f"Unsupported file extension: {extension}")
