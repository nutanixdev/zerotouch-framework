import pytest
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor

class TestStateMonitor(StateMonitor):
    def check_status(self):
        # Simulating different return values for check_status and testing against each case
        return_values_list = [
            ({"status": {"state": "test_state"}}, True),
            ({"status": {"state": "test_state"}}, False)
        ]
        self.call_count += 1
        return return_values_list[(self.call_count - 1) % 2]
    
    def test_monitor(self, mocker):
        self.call_count = 0
        
        result = self.monitor(query_retries=False)
        assert result == True
        result = self.monitor(query_retries=False)
        assert result == False
        result = self.monitor()
        assert result == ({"status": {"state": "test_state"}}, True)
        mock_sleep = mocker.patch("time.sleep")
        mock_time = mocker.patch("time.time")
        mock_logger = mocker.patch("framework.scripts.python.helpers.state_monitor.state_monitor.logger")
        mock_time.side_effect = [0,1801]
        result = self.monitor()
        mock_logger.error.assert_called_with("Timed out after 1801.00 seconds")
        assert result == (None, False)
        