import logging
import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.log_utils import ConfigureRootLogger, add_file_formatter, get_logger

class TestLogUtils:
    
    @patch('framework.helpers.log_utils.RainbowLoggingHandler')
    @patch('framework.helpers.log_utils.logging.FileHandler')
    @patch('framework.helpers.log_utils.logging.basicConfig')
    def test_configure_root_logger(self, mock_basicConfig, mock_FileHandler, mock_RainbowLoggingHandler):
        # Mock the RainbowLoggingHandler and FileHandler
        mock_ch = MagicMock()
        mock_fh = MagicMock()
        mock_RainbowLoggingHandler.return_value = mock_ch
        mock_FileHandler.return_value = mock_fh

        # Create an instance of ConfigureRootLogger
        logger = ConfigureRootLogger(debug=True, file_name="test.log")

        # Assert that the logging.basicConfig method is called with the correct arguments
        mock_basicConfig.assert_called_once_with(
            level=logging.DEBUG,
            handlers=[mock_ch, mock_fh]
        )

        # Assert that the setFormatter method is called with the correct argument
        mock_ch.setFormatter.assert_called_once()
        mock_fh.setFormatter.assert_called_once()


    @patch('framework.helpers.log_utils.RainbowLoggingHandler')
    @patch('framework.helpers.log_utils.logging.FileHandler')
    @patch('framework.helpers.log_utils.logging.basicConfig')
    def test_configure_root_logger_without_debug(self, mock_basicConfig, mock_FileHandler, mock_RainbowLoggingHandler):
        # Mock the RainbowLoggingHandler and FileHandler
        mock_ch = MagicMock()
        mock_fh = MagicMock()
        mock_RainbowLoggingHandler.return_value = mock_ch
        mock_FileHandler.return_value = mock_fh

        # Create an instance of ConfigureRootLogger without debug
        logger = ConfigureRootLogger(debug=False, file_name="test.log")

        # Assert that the logging.basicConfig method is called with the correct arguments
        mock_basicConfig.assert_called_once_with(
            level=logging.INFO,
            handlers=[mock_ch, mock_fh]
        )

        # Assert that the setFormatter method is called with the correct argument
        mock_ch.setFormatter.assert_called_once()
        mock_fh.setFormatter.assert_called_once()
    

    def test_add_file_formatter(self):
        # Mock the FileHandler
        mock_fh = MagicMock()

        # Create an instance of ConfigureRootLogger
        logger = ConfigureRootLogger(debug=True, file_name="test.log")

        # Call the add_file_formatter method with the mock FileHandler
        add_file_formatter(mock_fh)

        # Assert that the setFormatter method of the mock FileHandler is called with the correct argument
        mock_fh.setFormatter.assert_called_once()

    @patch('framework.helpers.log_utils.logging.getLogger')
    def test_get_logger(self, mock_getLogger):
        # Mock the logger returned by getLogger
        mock_logger = MagicMock()
        mock_getLogger.return_value = mock_logger

        # Call the get_logger method with a name and file_name
        logger = get_logger(name="test_logger", file_name="test.log")

        # Assert that the getLogger method is called with the correct argument
        mock_getLogger.assert_called_once_with("test_logger")

        # Assert that the addHandler method of the mock logger is called with the correct argument
        mock_logger.addHandler.assert_called_once()