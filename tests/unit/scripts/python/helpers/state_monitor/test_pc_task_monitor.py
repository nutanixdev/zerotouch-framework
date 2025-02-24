import pytest
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from framework.scripts.python.helpers.v3.task import Task
from unittest.mock import MagicMock

class TestPcTaskMonitor:
    @pytest.fixture
    def pc_task_monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return PcTaskMonitor(
            session=self.session, expected_state="test_state",
            task_uuid_list = ["test_uuid1", "test_uuid2", "test_uuid3", "test_uuid4", "test_uuid5"]
            )
    
    def test_pc_task_monitor_init(self, pc_task_monitor):
        assert isinstance(pc_task_monitor, PcTaskMonitor)
        assert isinstance(pc_task_monitor, StateMonitor)
        assert pc_task_monitor.session == self.session
        assert pc_task_monitor.expected_state == "test_state"
        assert pc_task_monitor.task_uuid_list == ["test_uuid1", "test_uuid2", "test_uuid3", "test_uuid4", "test_uuid5"]
        assert pc_task_monitor.completed_task_list == []
        assert pc_task_monitor.failed_task_list == []
        assert isinstance(pc_task_monitor.task_op, Task)
        assert pc_task_monitor.task_op.session == self.session
    
    def test_check_status(self, pc_task_monitor, mocker):
        mock_task_poll = mocker.patch.object(Task, 'poll')
        mock_task_poll.return_value = [
            {"status": "COMPLETED", "uuid":"test_uuid1"}, {"status": "FAILED", "uuid":"test_uuid2"}, {"status": "COMPLETED", "uuid":"test_uuid3"},
            {"status": "FAILED", "uuid":"test_uuid4"}, {"status": "COMPLETED", "uuid":"test_uuid5"}
            ]
        assert pc_task_monitor.check_status() == ("[{'status': 'FAILED', 'uuid': 'test_uuid2'}, {'status': 'FAILED', 'uuid': 'test_uuid4'}]", True)
        mock_task_poll.return_value = [
            {"status": "COMPLETED", "uuid":"test_uuid1"}, {"status": "COMPLETED", "uuid":"test_uuid2"}, {"status": "COMPLETED", "uuid":"test_uuid3"},
            {"status": "COMPLETED", "uuid":"test_uuid4"}, {"status": "COMPLETED", "uuid":"test_uuid5"}
            ]
        assert pc_task_monitor.check_status() == (None, True)
        pc_task_monitor.task_uuid_list = []
        assert pc_task_monitor.check_status() == (None, True)

    def test__uuid_list_chunks(self, pc_task_monitor):
        uuid_list = ["uuid1", "uuid2", "uuid3", "uuid4", "uuid5"]
        chunks = list(pc_task_monitor._PcTaskMonitor__uuid_list_chunks(uuid_list, chunk_size=2))
        assert chunks == [["uuid1", "uuid2"], ["uuid3", "uuid4"], ["uuid5"]]
        
        
        