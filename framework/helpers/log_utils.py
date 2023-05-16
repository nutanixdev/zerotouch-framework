import logging
import time
import sys
from typing import Union
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
        self._fh = logging.FileHandler("script_log.log", mode='w')

        # add formatter to console handler
        self.__add_console_formatter(self._ch)

        # add formatter to file handler
        self.__add_file_formatter(self._fh)

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

    @staticmethod
    def __add_file_formatter(fh: logging.FileHandler):
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


def get_logger(name):
    """returns a new logger"""

    logging_handle = logging.getLogger(name)
    return logging_handle
