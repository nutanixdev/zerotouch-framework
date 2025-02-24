import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.workflow_utils import Workflow

class TestWorkflow:
    def test_run_scripts(self):
        # Create a mock script class
        mock_script = MagicMock()
        # Create an instance of Workflow
        workflow = Workflow()
        # Call the run_scripts method with the mock script class
        workflow.run_scripts([mock_script])
        # Assert that the logger.info method is called with the correct argument
        mock_script.assert_called_once_with(data = {})
    
    def test_run_functions(self):
        # Create a mock function
        mock_function = MagicMock()
        mock_function.__name__ = 'mock_function'
        # Create an instance of Workflow
        workflow = Workflow()
        # Call the run_functions method with the mock function
        workflow.run_functions([mock_function])
        # Assert that the logger.info method is called with the correct argument
        mock_function.assert_called_once_with({})