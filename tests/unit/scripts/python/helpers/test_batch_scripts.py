import pytest
from unittest.mock import patch, MagicMock
from framework.scripts.python.helpers.batch_script import BatchScript
from framework.scripts.python.script import Script

class TestBatchScripts:
    @pytest.fixture
    def batch_script(self):
        return BatchScript(results_key="results", parallel=True, max_workers=4)
    
    def test_batch_script_init(self, batch_script):
        assert batch_script.script_list == []
        assert batch_script._results == {}
        assert batch_script.results_key == "results"
        assert batch_script.max_workers == 4
        assert batch_script._parallel == True
        assert isinstance(batch_script, BatchScript)
        assert isinstance(batch_script, Script)
        
    def test_batch_script_results(self, batch_script):
        assert batch_script.results == {}
        
    def test_batch_script_consolidate_results(self, batch_script):
        new_item = {"key1": {"subkey1": "subvalue1"}, "key2": "value2"}
        initial_results = {"key1": {"subkey1": "old_value"}, "key3": "value3"}
        expected_result = {"key1": {"subkey1": "subvalue1"}, "key2": "value2", "key3": "value3"}

        result = batch_script.consolidate_results(new_item = new_item, results = initial_results)
        assert result == expected_result
    
    def test_results_setter(self, batch_script):
        batch_script.results = None
        assert batch_script._results == {}
        
        batch_script.results = "item1"
        assert batch_script._results == {"results": ["item1"]}
    
        batch_script.results = "item2"
        assert batch_script._results == {"results": ["item1", "item2"]}
        
        new_item = {"key1": "value1", "key2": {"subkey1": "subvalue1"}}
        batch_script.results = new_item
        expected_result = {'results': ['item1', 'item2'], "key1": "value1", "key2": {"subkey1": "subvalue1"}}
        assert batch_script._results == expected_result
    
    def test_add_script(self, batch_script, mocker):
        script = MagicMock()
        batch_script.add(script)
        assert script in batch_script.script_list

        mock_logger = mocker.patch("framework.scripts.python.helpers.batch_script.logger")

        batch_script.add(None)
        mock_logger.error.assert_called_with("Script is none, returning.")

    def test_add_all_scripts(self, batch_script):
        script1 = MagicMock()
        script2 = MagicMock()
        script_list = [script1, script2]
        batch_script.add_all(script_list)
        assert script1 in batch_script.script_list
        assert script2 in batch_script.script_list

    def test_run(self, batch_script, mocker):
        mock_sequential_execute = mocker.patch.object(BatchScript, "_sequential_execute")
        mock_parallel_execute = mocker.patch.object(BatchScript, "_parallel_execute")
        batch_script.run()
        mock_parallel_execute.assert_called_once()
        batch_script._parallel = False
        batch_script.run()
        mock_sequential_execute.assert_called_once()
        
    def test_sequential_execute(self, batch_script):
        script1 = MagicMock()
        script1.run.return_value = {"result1": "value1"}
        script2 = MagicMock()
        script2.run.return_value = {"result2": "value2"}

        batch_script.add(script1)
        batch_script.add(script2)

        batch_script._sequential_execute()

        assert batch_script.results == {"result1": "value1", "result2": "value2"}
        script1.run.assert_called_once()
        script2.run.assert_called_once()

    def test_parallel_execute(self, batch_script, mocker):
        mock_executor = mocker.patch("concurrent.futures.ThreadPoolExecutor")
        script1 = MagicMock()
        script1.run.return_value = {"result1": "value1"}
        script2 = MagicMock()
        script2.run.return_value = {"result2": "value2"}

        batch_script.add(script1)
        batch_script.add(script2)

        mock_executor.return_value.__enter__.return_value.map.return_value = [script1.run(), script2.run()]

        batch_script._parallel_execute()

        assert batch_script.results == {"result1": "value1", "result2": "value2"}
        script1.run.assert_called_once()
        script2.run.assert_called_once()
        mock_executor.assert_called_once_with(max_workers=batch_script.max_workers)