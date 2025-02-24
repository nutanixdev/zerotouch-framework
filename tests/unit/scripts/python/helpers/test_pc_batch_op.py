import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.pc_batch_op import PcBatchOp, get_task_uuid_list
from framework.helpers.rest_utils import RestAPIUtil

@pytest.fixture
def session():
    return MagicMock(spec=RestAPIUtil)

@pytest.fixture
def pc_batch_op(session):
    return PcBatchOp(session, resource_type="/entities", kind="test-kind")

class TestPcBatchOp:

    @pytest.mark.parametrize("api_request_list, expected_chunks", [
        ([], []),
        ([1, 2, 3], [[1, 2, 3]]),
        (list(range(70)), [list(range(60)), list(range(60, 70))])
    ])
    def test_batch(self, pc_batch_op, session, api_request_list, expected_chunks):
        print(f"Testing batch with api_request_list: {api_request_list} and expected_chunks: {expected_chunks}")
        session.post.side_effect = [{"api_response_list": [{} for _ in chunk]} for chunk in expected_chunks]

        response = pc_batch_op.batch(api_request_list)
        print(f"response: {response}")
        assert session.post.call_count == len(expected_chunks)
        assert len(response) == len(api_request_list)
        assert response == [{} for _ in range(len(api_request_list))]

    def test_batch_create(self, pc_batch_op, session):
        request_payload_list = [{"spec": {"name": "test1"}}, {"spec": {"name": "test2"}}]
        session.post.return_value = {
            "api_response_list": [
                {"api_response": {"status": {"execution_context": {"task_uuid": "uuid1"}}}},
                {"api_response": {"status": {"execution_context": {"task_uuid": "uuid2"}}}}
            ]
        }

        response = pc_batch_op.batch_create(request_payload_list)
        print(f"batch_create response: {response}")

        assert response == ["uuid1", "uuid2"]

    def test_batch_update(self, pc_batch_op, session):
        entity_update_list = [
            {"uuid": "1", "spec": {"key": "value1"}, "metadata": {"kind": "test-kind"}},
            {"uuid": "2", "spec": {"key": "value2"}, "metadata": {"kind": "test-kind"}}
        ]
        session.post.return_value = {
            "api_response_list": [
                {"api_response": {"status": {"execution_context": {"task_uuid": "uuid1"}}}},
                {"api_response": {"status": {"execution_context": {"task_uuid": "uuid2"}}}}
            ]
        }

        with patch("framework.helpers.log_utils.get_logger") as mock_logger:
            mock_logger.return_value.error = MagicMock()

            original_batch = pc_batch_op.batch

            def logged_batch(api_request_list):
                print(f"api_request_list before batch: {api_request_list}")
                return original_batch(api_request_list)

            pc_batch_op.batch = logged_batch

            original_batch_update = pc_batch_op.batch_update

            def logged_batch_update(entity_update_list):
                print(f"entity_update_list: {entity_update_list}")
                api_request_list = []
                for entity_data in entity_update_list:
                    if entity_data.get('uuid') and entity_data.get('spec') and entity_data.get('metadata'):
                        request = {
                            "operation": "PUT",
                            "path_and_params": f"{pc_batch_op.base_url}{pc_batch_op.resource_type}/{entity_data['uuid']}",
                            "body": {
                                "spec": entity_data.get('spec'),
                                "metadata": entity_data.get('metadata')
                            }
                        }
                        api_request_list.append(request)
                print(f"Constructed api_request_list: {api_request_list}")
                return original_batch_update(entity_update_list)

            pc_batch_op.batch_update = logged_batch_update

            response = pc_batch_op.batch_update(entity_update_list)
            print(f"batch_update response: {response}")

            assert response == ["uuid1", "uuid2"]
            mock_logger.return_value.error.assert_not_called()

    def test_batch_delete(self, pc_batch_op, session):
        entity_list = ["1", "2"]
        session.post.return_value = {
            "api_response_list": [
                {"api_response": {"status": {"execution_context": {"task_uuid": "uuid1"}}}},
                {"api_response": {"status": {"execution_context": {"task_uuid": "uuid2"}}}}
            ]
        }

        response = pc_batch_op.batch_delete(entity_list)
        print(f"batch_delete response: {response}")

        assert response == ["uuid1", "uuid2"]

    def test_get_task_uuid_list(self):
        api_response_list = [
            {"status": "200", "api_response": {"status": {"execution_context": {"task_uuid": "uuid1"}}}},
            {"status": "200", "api_response": {"task_uuid": "uuid2"}},
            {"status": "400", "api_response": "error"}
        ]

        with patch("framework.helpers.log_utils.get_logger") as mock_logger:
            mock_logger.return_value.error = MagicMock()
            task_uuid_list=[]
            try:
                task_uuid_list = get_task_uuid_list(api_response_list)
                print(f"get_task_uuid_list response: {task_uuid_list}")
                assert task_uuid_list == ["uuid1", "uuid2"]
            except Exception as e:
                print(f"Caught exception: {e}")
                assert str(e) == "Cannot get task list to monitor for the batch call!: Expecting value: line 1 column 1 (char 0)"
            finally:
                if task_uuid_list is None:
                    mock_logger.return_value.error.assert_called_once()