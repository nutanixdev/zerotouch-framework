import ntnx_prism_py_client
import uuid

from typing import List, Optional
from framework.helpers.log_utils import get_logger
from framework.helpers.v4_api_client import ApiClientV4
from ntnx_prism_py_client.models.prism.v4.operations.BatchSpec import BatchSpec
from ntnx_prism_py_client.models.prism.v4.operations.BatchSpecMetadata import BatchSpecMetadata
from ntnx_prism_py_client.models.prism.v4.operations.BatchSpecPayload import BatchSpecPayload
from ntnx_prism_py_client.models.prism.v4.operations.BatchSpecMetadata import BatchSpecMetadata
from ntnx_prism_py_client.models.prism.v4.operations.BatchSpecPayload import BatchSpecPayload
from ntnx_prism_py_client.models.prism.v4.operations.BatchSpecPayloadMetadata import BatchSpecPayloadMetadata
from ntnx_prism_py_client.models.prism.v4.operations.BatchSpecPayloadMetadataHeader import BatchSpecPayloadMetadataHeader
from ntnx_prism_py_client.models.prism.v4.operations.BatchSpecPayloadMetadataPath import  BatchSpecPayloadMetadataPath
from ntnx_prism_py_client.models.prism.v4.operations.ActionType import ActionType

logger = get_logger(__name__)

BATCH_TIMEOUT = (5, 6 * 60)
MAX_BATCH_API_CALLS = 60


class PcBatchOpv4:
    """
    This is helper class to do v4 Batch api calls.
    """
    BATCH_BASE = "batch"
    PAYLOAD = {
        "action_on_failure": "CONTINUE",
        "execution_order": "SEQUENTIAL",
        "api_request_list": []
    }

    def __init__(self, v4_api_util: ApiClientV4, **kwargs):
        """
        Default Constructor for PcBatchOp class
        """
        self.base_url = "/api"
        self.resource_type = kwargs.get("resource_type")
        self.client = v4_api_util.get_api_client("prism")
        self.batch_api = ntnx_prism_py_client.BatchesApi(
            api_client=self.client
            )

    def batch_create(self, request_payload_list: Optional[List]):
        """
        Create entities using v4 batch api

        Args:
          request_payload_list(list): request payload dict including spec,
            metadata and api_version

        Returns:
          list:  List of Task UUIDs
        """
        unique_id = uuid.uuid1()
        
        batch_spec_payload_list = [
            BatchSpecPayload(data=batch_spec_payload)
            for batch_spec_payload in request_payload_list
        ]

        batch_spec = BatchSpec(
            metadata=BatchSpecMetadata(
                action=ActionType.CREATE,
                name=f"multi_{unique_id}",
                uri=f"{self.base_url}/{self.resource_type}",
                stop_on_error=True,
                chunk_size=1,
            ),
            payload=batch_spec_payload_list,
        )
        api_response_list = self.batch_api.submit_batch(
                async_req=False, body=batch_spec
            )

        return get_task_uuid_list(api_response_list)

    def batch_delete(self, entity_list: List):
        """
        Create entities using v3 batch api

        Args:
          entity_list(list): each element is a tuple of ext_id and etag

        Returns:
          list:  List of Task UUIDs
        """
        unique_id = uuid.uuid1()
        batch_spec_payload_list = [
            BatchSpecPayload(
            data=None,
            metadata=BatchSpecPayloadMetadata(
                headers=[
                BatchSpecPayloadMetadataHeader(
                    name="If-Match", value=batch_spec_payload[1]
                )
                ],
                path=[
                BatchSpecPayloadMetadataPath(
                    name="extId", value=batch_spec_payload[0]
                )
                ],
            )
            )
            for batch_spec_payload in entity_list
        ]

        batch_spec = BatchSpec(
            metadata=BatchSpecMetadata(
                action=ActionType.DELETE,
                name=f"multi_{unique_id}",
                uri=f"{self.base_url}/{self.resource_type}/{{extId}}",
                stop_on_error=True,
                chunk_size=1,
            ),
            payload=batch_spec_payload_list,
        )
        api_response_list = self.batch_api.submit_batch(
                async_req=False, body=batch_spec
            )

        return get_task_uuid_list(api_response_list)

    def batch_update(self, entity_update_list: Optional[List]):
        """
        Create entities using v4 batch api

        Args:
          entity_update_list(list): List of payload dict including spec,
            metadata and ext_id

        Returns:
          list:  List of Task UUIDs
        """
        unique_id = uuid.uuid1()

        batch_spec_payload_list = [
            BatchSpecPayload(
                data=batch_spec_payload[0],
                metadata=BatchSpecPayloadMetadata(
                    headers=[
                        BatchSpecPayloadMetadataHeader(
                            name="If-Match", 
                            value=batch_spec_payload[1]
                        )
                    ],
                    path=[
                        BatchSpecPayloadMetadataPath(
                            name="extId", 
                            value=batch_spec_payload[0].ext_id
                        )
                    ],
                )
            )
            for batch_spec_payload in entity_update_list
        ]

        batch_spec = BatchSpec(
            metadata=BatchSpecMetadata(
                action=ActionType.MODIFY,
                name=f"multi_{unique_id}",
                uri=f"{self.base_url}/{self.resource_type}/{{extId}}",
                stop_on_error=True,
                chunk_size=1,
            ),
            payload=batch_spec_payload_list,
        )
        
        api_response_list = self.batch_api.submit_batch(
                async_req=False, body=batch_spec
            )

        return get_task_uuid_list(api_response_list)


def get_task_uuid_list(api_response_list: List) -> List:
    """
    Parse the batch api response list to get the Task uuids
    Args:
      api_response_list(list): Batch api response list
    Returns:
      list : list of Task uuids
    """
    task_uuid_list = []
    
    task_uuid_list.append(api_response_list.data.ext_id)
    return task_uuid_list
