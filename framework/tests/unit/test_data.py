import logging
import json

LOGGER = logging.getLogger(__name__)

API_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

REST_ARGS = {
    "ip_address": "1.1.1.1",
    "user": "user",
    "pwd": "pwd",
    "headers": API_HEADERS,
    "port": 9440
}

REST_URI = "api/fc/v1/imaged_nodes/list"

API_PAYLOAD = {
    "filters": {
        "node_state": "STATE_AVAILABLE"
    }
}

GET_RESPONSE = POST_RESPONSE = json.dumps({
    "entities": [
        {
            "type": "News articles",
            "id": "1",
            "attributes": {
                "title": "JSON:API paints my bikeshed!",
                "body": "The shortest article. Ever.",
                "created": "2015-05-22T14:56:29.000Z",
                "updated": "2015-05-22T14:56:28.000Z"
            },
            "relationships": {
                "author": {
                    "data": {
                        "id": "42",
                        "type": "people"
                    }
                }
            }
        },
        {
            "type": "Journals",
            "id": "2",
            "attributes": {
                "title": "JSON:API paints my bikeshed!",
                "body": "The shortest article. Ever.",
                "created": "2016-05-22T14:56:29.000Z",
                "updated": "2016-05-22T14:56:28.000Z"
            },
            "relationships": {
                "author": {
                    "data": {
                        "id": "42",
                        "type": "people"
                    }
                }
            }
        },
        {
            "type": "Publishes",
            "id": "3",
            "attributes": {
                "title": "JSON:API paints my bikeshed!",
                "body": "The shortest article. Ever.",
                "created": "2017-05-22T14:56:29.000Z",
                "updated": "2017-05-22T14:56:28.000Z"
            }
        }
    ]
})
