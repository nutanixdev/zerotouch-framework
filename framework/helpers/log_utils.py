import logging
import time
import sys
from typing import Optional
from rainbow_logging_handler import RainbowLoggingHandler


class ConfigureRootLogger:
    """
    customization the root logger
    """

    def __init__(self, debug: False):
        """
        Build CustomLogger based on logging module

        Args:
           debug: If we want to set debug or not

        Returns:
           None
        """
        # create console handler
        self._ch = RainbowLoggingHandler(sys.stderr, color_message_info=('green', None, False))

        # create file handler
        self._fh = logging.FileHandler("zero_touch.log", mode='w')

        # add formatter to console handler
        self.__add_console_formatter(self._ch)

        # add formatter to file handler
        add_file_formatter(self._fh)

        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level,
            handlers=[self._ch, self._fh]
        )

    @staticmethod
    def __add_console_formatter(ch: RainbowLoggingHandler):
        """
        add ColorFormatter with custom colors for each log level

        Args:
            ch

        Returns
            None
        """

        fmt = (
            "[%(asctime)s] "
            "[%(threadName)s] "
            "[%(levelname)s] %(message)s"
        )

        formatter = logging.Formatter(fmt)
        formatter.converter = time.gmtime

        # add formatter to console handler
        ch.setFormatter(formatter)


def add_file_formatter(fh: logging.FileHandler):
    """
    add file formatter with custom colors for each log level

    Args:
        fh

    Returns
        None
    """
    fmt = (
        "[%(asctime)s] "
        "[%(threadName)s] "
        "[%(levelname)s] "
        "[%(module)s.%(funcName)s():%(lineno)s] %(message)s"
    )

    formatter = logging.Formatter(fmt)
    formatter.converter = time.gmtime

    # add formatter to file handler
    fh.setFormatter(formatter)


def get_logger(name: str, file_name: Optional[str] = None):
    """returns a new logger"""

    logging_handle = logging.getLogger(name)
    # We are taking file_name as optional parameter. If file_name is passed, we'll create a new Filehandler and add
    # this filename to the handler. By doing this, the logger will write to the new file along with the
    # pre-configured root logger file i.e. zero_touch.log
    if file_name:
        fh = logging.FileHandler(file_name, mode='w')
        add_file_formatter(fh)
        if fh not in logging_handle.handlers:
            logging_handle.addHandler(fh)

    return logging_handle
