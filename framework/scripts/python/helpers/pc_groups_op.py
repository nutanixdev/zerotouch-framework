from typing import Optional
from framework.helpers.rest_utils import RestAPIUtil

GROUP_MEMBER_COUNT_THRESHOLD = 500


class PcGroupsOp:
    """
    The API wrapper class for Groups API call
    """
    GROUP_BASE = "groups"

    def __init__(self, session: RestAPIUtil, base_path: Optional[str] = None):
        """
        Default Constructor for PcGroupsOp class
        Args:
          session: PC session object
        """
        self.session = session
        self.base_path = base_path

    def list_entities(self, **kwargs):
        """
        Get all the entities

        Args(kwargs):
          attributes(list<str>): The list of attributes to return
          entity_type(str): The type of the entity
          group_member_count_threshold(int): max items to fetch by groups api call
          filter_criteria(csv): filter criteria list as a string
            example - "filter_criteria":"vm_name==name1,vm_name==name2"
        Returns:
          list<dict>: The event list.
        """
        group_member_offset = 0
        # Note - this will work even if entity count is less than 2500
        group_member_count_threshold = kwargs.pop("group_member_count_threshold",
                                                  GROUP_MEMBER_COUNT_THRESHOLD)
        # max is 500
        group_member_count_threshold = min(group_member_count_threshold,
                                           GROUP_MEMBER_COUNT_THRESHOLD)
        entities_json = []
        obtained_entities_count = kwargs.pop("obtained_entities_count", None)
        response = self.__groups_post_call(
            group_member_offset, group_member_count_threshold, **kwargs)
        entities_json.extend(self.__parse_response(response))
        total_entity_count = response.get("total_entity_count")
        filtered_entity_count = response.get("filtered_entity_count", None)
        if filtered_entity_count is not None and kwargs.get("filter_criteria") is not None:
            # When using filters with groups call, use filtered_entity_count as total.
            total_entity_count = filtered_entity_count
        if obtained_entities_count:
            total_entity_count = min(total_entity_count, obtained_entities_count)
        if total_entity_count > group_member_count_threshold:
            while True:
                group_member_offset = group_member_offset + group_member_count_threshold
                if group_member_offset >= total_entity_count:
                    break
                response = self.__groups_post_call(
                    group_member_offset, group_member_count_threshold, **kwargs)
                entities_json.extend(self.__parse_response(response))
        return entities_json

    def list_dvs(self, cluster_uuid: str):
        """
        Get the distributed_virtual_switch from a cluster

        Args:
          cluster_uuid(str): PE Cluster UUID

        Returns:
          list
        """
        attributes = ["name", "default", "cluster_configuration_list.cluster_uuid"]
        filter_criteria = f"cluster_configuration_list.cluster_uuid=cs={cluster_uuid}"
        return self.list_entities(entity_type="distributed_virtual_switch",
                                  attributes=attributes,
                                  filter_criteria=filter_criteria)

    def __groups_post_call(self, group_member_offset, group_member_count, **kwargs):
        """
        Helper to perform prism client post request

        Args:
          group_member_offset(int): offset to fetch entities in groups api
          group_member_count(int):  number of entities to get from groups api
          (kwargs):
            attributes(list<str>): The list of attributes to return
            entity_type(str): The type of the entity
            group_member_count_threshold(int): max items to fetch by groups api call
            filter_criteria(csv): filter criteria list as a string
              example - "filter_criteria":"vm_name==name1|name2"
        Returns:
          entities_json(list): list of entities json
        """
        group_member_attributes = [{"attribute": name} for name in
                                   kwargs.pop("attributes", [])]
        group_attributes = kwargs.pop("group_attributes", None)
        grouping_attribute = kwargs.pop("grouping_attribute", None)
        group_member_sort_order = kwargs.pop("group_member_sort_order", None)
        group_member_sort_attribute = kwargs.pop("group_member_sort_attribute",
                                                 None)
        interval_start_ms = kwargs.pop("interval_start_ms", None)
        interval_end_ms = kwargs.pop("interval_end_ms", None)
        downsampling_interval = kwargs.pop("downsampling_interval", None)
        group_count = kwargs.pop("group_count", None)
        filter_criteria = kwargs.pop("filter_criteria", None)
        az_scope = kwargs.pop("az_scope", None)
        entity_ids = kwargs.pop("entity_ids", None)
        query_str = kwargs.pop("query_str", None)

        payload = {
            "entity_type": kwargs.pop("entity_type"),
            "group_member_attributes": group_member_attributes
        }
        if entity_ids:
            payload.update({"entity_ids": entity_ids})
        if filter_criteria:
            payload.update({"filter_criteria": filter_criteria})
        if group_attributes:
            payload.update({"group_attributes": group_attributes})
        if grouping_attribute:
            payload.update({"grouping_attribute": grouping_attribute})
        if group_member_sort_attribute:
            payload.update(
                {"group_member_sort_attribute": group_member_sort_attribute})
        if group_member_sort_order:
            payload.update({"group_member_sort_order": group_member_sort_order})
        if interval_start_ms:
            payload.update({"interval_start_ms": interval_start_ms})
        if interval_end_ms:
            payload.update({"interval_end_ms": interval_end_ms})
        if downsampling_interval:
            payload.update({"downsampling_interval": downsampling_interval})
        if group_count:
            payload.update({"group_count": group_count})
        payload.update({"group_member_count": group_member_count})
        payload.update({"group_member_offset": group_member_offset})
        if az_scope:
            payload.update({"availability_zone_scope": az_scope})

        if query_str:
            url = f"{self.GROUP_BASE}?{query_str}"
        else:
            url = f"{self.GROUP_BASE}"

        if self.base_path:
            url = f"{self.base_path}/{url}"

        response = self.session.post(
            uri=url,
            data=payload
        )
        return response

    @staticmethod
    def __parse_response(response):
        """
        Helper to parse the json response from Groups api call

        Args:
          response(dict): json response from prism client
        Returns:
          entities_json(list): list of entities json
        """
        entities_json = []
        if response.get("group_results"):
            group_result = response.get("group_results")[0]
            entity_results = group_result.get("entity_results", [])
            if not entity_results:
                return entities_json
            for entity_result in entity_results:
                entity = dict()
                entity["uuid"] = entity_result.get("entity_id")
                for data in entity_result.get("data", []):
                    if data.get("values") and data.get("values")[0].get("values"):
                        if len(data.get("values")[0].get("values")) == 1:
                            entity[data.get("name")] = data.get("values")[0].get("values")[0]
                        else:
                            entity[data.get("name")] = data.get("values")[0].get("values")
                entities_json.append(entity)
        return entities_json
