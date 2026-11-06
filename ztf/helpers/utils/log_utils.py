"""Logging utility helpers for ZTF helper modules."""

import logging
import os

_file_log_format = "%(asctime)s %(levelname)s [%(module)s:%(lineno)d] %(message)s"


def add_file_formatter(handler: logging.FileHandler) -> None:
    """Attach a file log formatter to *handler*.

    The formatter includes ``%(module)s`` so that the originating module name
    is recorded in every file log entry.

    Args:
        handler: A :class:`logging.FileHandler` to configure.
    """
    handler.setFormatter(logging.Formatter(_file_log_format))


def get_logger(name: str, file_name: str | None = None) -> logging.Logger:
    """Return a named logger, optionally writing to *file_name*.

    Args:
        name: Logger name (typically ``__name__``).
        file_name: Optional path for a dedicated file handler.

    Returns:
        Configured :class:`logging.Logger`.
    """
    logger = logging.getLogger(name)

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        logger.addHandler(stream_handler)

    if file_name is not None and not any(
        isinstance(h, logging.FileHandler) for h in logger.handlers
    ):
        log_dir = os.path.dirname(file_name)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(file_name)
        file_handler.setLevel(logging.DEBUG)
        add_file_formatter(file_handler)
        logger.addHandler(file_handler)

    return logger
