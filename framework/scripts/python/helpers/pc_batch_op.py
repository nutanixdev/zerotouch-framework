import copy
import json
from typing import List, Optional
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil

logger = get_logger(__name__)

BATCH_TIMEOUT = (5, 6 * 60)
MAX_BATCH_API_CALLS = 60


class PcBatchOp:
    """
    This is helper class to do V3 Batch api calls.
    """
    BATCH_BASE = "batch"
    PAYLOAD = {
        "action_on_failure": "CONTINUE",
        "execution_order": "SEQUENTIAL",
        "api_request_list": []
    }

    def __init__(self, session: RestAPIUtil, **kwargs):
        """
        Default Constructor for PcBatchOp class
        Args:
          session: PC session object
          base_url (str): URL_BASE of the Entity
          kind (str): V3_KIND of the Entity
        """
        self.session = session
        # Batch APIs are failing for "api/nutanix/v3" hence adding an escape character for /v
        self.base_url = "api/nutanix//v3"
        self.resource_type = kwargs.get("resource_type")
        self.kind = kwargs.get("kind")

    def batch(self, api_request_list: List):
        """
        Call batch API
        Args:
          api_request_list (list): Payload for batch
        Returns:
          list of api_response_list
        """
        api_request_chunks = [
            api_request_list[i:i + MAX_BATCH_API_CALLS]
            for i in range(0, len(api_request_list), MAX_BATCH_API_CALLS)
        ]

        api_response_list = []
        for request_list in api_request_chunks:
            payload = copy.deepcopy(self.PAYLOAD)

            payload["api_request_list"] = request_list
            logger.debug("Batch Payload: {}".format(payload))

            batch_response = self.session.post(
                uri=f"{self.base_url}/{self.BATCH_BASE}",
                data=payload,
                timeout=BATCH_TIMEOUT
            )
            if batch_response.get('api_response_list', None):
                api_response_list.extend(batch_response.get('api_response_list'))
        return api_response_list

    def batch_create(self, request_payload_list: Optional[List]):
        """
        Create entities using v3 batch api

        Args:
          request_payload_list(list): request payload dict including spec,
            metadata and api_version

        Returns:
          list:  List of Task UUIDs
        """
        api_request_payload = {
            "operation": "POST",
            "path_and_params": f"{self.base_url}{self.resource_type}",
            "body": {
            }
        }

        api_request_list = []
        if request_payload_list:
            for request_payload in request_payload_list:
                api_request = copy.deepcopy(api_request_payload)

                if request_payload.get("spec"):
                    api_request["body"]["spec"] = request_payload.get("spec", None)
                    api_request["body"]["metadata"] = request_payload.get("metadata", {"kind": self.kind})
                else:
                    api_request["body"] = request_payload
                api_request_list.append(api_request)
        api_response_list = self.batch(api_request_list)

        return get_task_uuid_list(api_response_list)

    def batch_update(self, entity_update_list: List):
        """
        Batch update an entity
        Args:
          entity_update_list (list): List of dicts with uuid, spec and metadata
          eg, [{
            "uuid": uuid, "spec": spec, "metadata": metadata}}
          , ..]
        Returns:
          list : Task UUID list
        """
        api_request_list = []
        for entity_data in entity_update_list:
            if entity_data.get('uuid') and entity_data.get('spec') and entity_data.get('metadata'):
                request = {
                    "operation": "PUT",
                    "path_and_params": f"{self.base_url}{self.resource_type}/{entity_data['uuid']}",
                    "body": {
                        "spec": entity_data.get('spec'),
                        "metadata": entity_data.get('metadata')
                    }
                }
                api_request_list.append(request)

        api_response_list = self.batch(api_request_list)
        return get_task_uuid_list(api_response_list)


def get_task_uuid_list(api_response_list: List):
    """
    Parse the batch api response list to get the Task uuids
    Args:
      api_response_list(list): Batch api response list
    Returns:
      list : list of Task uuids
    """
    task_uuid_list = []
    for response in api_response_list:
        if response.get("status"):
            if not response["status"].startswith("2"):
                logger.error(response)

        api_response = response.get("api_response")

        # todo bug
        # sometimes api_response in str
        if type(api_response) == str:
            try:
                api_response = json.loads(api_response)
            except Exception as e:
                raise Exception(f"Cannot get task list to monitor for the batch call!: {e}")

        if api_response.get('status', {}).get('execution_context', {}).get('task_uuid'):
            task_uuid = api_response['status']['execution_context']['task_uuid']
            task_uuid_list.append(task_uuid)
        # In some cases only task_uuid is returned in response
        elif api_response.get('task_uuid', {}):
            task_uuid = api_response["task_uuid"]
            task_uuid_list.append(task_uuid)

    return task_uuid_list
