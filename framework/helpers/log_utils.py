import logging
import time
import sys
from typing import Optional
from rainbow_logging_handler import RainbowLoggingHandler


class ConfigureRootLogger:
    """
    Customization of the root logger.
    """

    def __init__(self, debug: bool = False, file_name: str = "zero_touch.log"):
        """
        Build CustomLogger based on logging module.

        Args:
            debug (bool): If we want to set debug or not.
            file_name (str): Name of the log file.
        """
        # create console handler
        self._ch = RainbowLoggingHandler(sys.stderr, color_message_info=('green', None, False))

        # create file handler
        self._fh = logging.FileHandler(file_name, mode='w')

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
    def __add_console_formatter(ch: RainbowLoggingHandler) -> None:
        """
        Add ColorFormatter with custom colors for each log level.

        Args:
            ch (RainbowLoggingHandler): Console handler to add formatter to.
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


def add_file_formatter(fh: logging.FileHandler) -> None:
    """
    Add file formatter with custom colors for each log level.

    Args:
        fh (logging.FileHandler): File handler to add formatter to.
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


def get_logger(name: str, file_name: Optional[str] = None) -> logging.Logger:
    """
    Returns a new logger.

    Args:
        name (str): Name of the logger.
        file_name (Optional[str]): Optional file name for the logger.

    Returns:
        logging.Logger: Configured logger.
    """
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
