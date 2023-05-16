from copy import deepcopy

from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pc_entity import PcEntity
from scripts.python.helpers.v3.address_group import AddressGroup
from scripts.python.helpers.v3.service_group import ServiceGroup
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class SecurityPolicy(PcEntity):
    kind = "network_security_rule"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/network_security_rules"
        self.session = session
        super(SecurityPolicy, self).__init__(session)

    def _get_default_spec(self):
        return deepcopy(
            {
                "metadata": {"kind": "network_security_rule"},
                "spec": {
                    "name": None,
                    "resources": {"is_policy_hitlog_enabled": False},
                },
            }
        )

    def create_security_policy_spec(self, sp_info):
        spec = self._get_default_spec()
        # Get the name
        self._build_spec_name(spec, sp_info["name"])
        # Get description
        self._build_spec_desc(spec, sp_info.get("description"))

        self._build_allow_ipv6_traffic(spec, sp_info.get("allow_ipv6_traffic", False))

        self._build_is_policy_hitlog_enabled(spec, sp_info.get("hitlog", True))

        # App policy
        self._build_app_rule(spec, sp_info.get("app_rule"))

        return spec

    @staticmethod
    def _build_spec_name(payload, value):
        payload["spec"]["name"] = value
        return payload, None

    @staticmethod
    def _build_spec_desc(payload, value):
        payload["spec"]["description"] = value
        return payload, None

    @staticmethod
    def _build_allow_ipv6_traffic(payload, value):
        payload["spec"]["resources"]["allow_ipv6_traffic"] = value
        return payload, None

    @staticmethod
    def _build_is_policy_hitlog_enabled(payload, value):
        payload["spec"]["resources"]["is_policy_hitlog_enabled"] = value
        return payload, None

    def _build_app_rule(self, payload, value):
        app_rule = payload["spec"]["resources"].get("app_rule", {})
        payload["spec"]["resources"]["app_rule"] = self._build_spec_rule(
            app_rule, value
        )
        return payload, None

    def _build_spec_rule(self, payload, value):
        rule = payload

        if value.get("target_group"):
            target_group = {}
            params = {}
            categories = value["target_group"].get("categories", {})
            if categories.get("ADGroup"):
                params["ADGroup"] = [categories["ADGroup"]]
                if value["target_group"].get("default_internal_policy"):
                    target_group["default_internal_policy"] = value["target_group"][
                        "default_internal_policy"
                    ]
            if categories.get("AppType"):
                params["AppType"] = [categories["AppType"]]
            if categories.get("AppTier"):
                params["AppTier"] = [categories.get("AppTier")]
                if value["target_group"].get("default_internal_policy"):
                    target_group["default_internal_policy"] = value["target_group"][
                        "default_internal_policy"
                    ]
            if categories.get("apptype_filter_by_category"):
                params.update(**categories["apptype_filter_by_category"])

            target_group["filter"] = (
                payload.get("target_group", {}).get("filter")
                or self._get_default_filter_spec()
            )
            if params:
                target_group["filter"]["params"] = params
            target_group["peer_specification_type"] = "FILTER"
            payload["target_group"] = target_group

        if value.get("inbounds"):
            rule["inbound_allow_list"] = self._generate_bound_spec(
                rule.get("inbound_allow_list", []), value["inbounds"]
            )
        elif value.get("allow_all_inbounds"):
            rule["inbound_allow_list"] = [{"peer_specification_type": "ALL"}]
        if value.get("outbounds"):
            rule["outbound_allow_list"] = self._generate_bound_spec(
                rule.get("outbound_allow_list", []), value["outbounds"]
            )
        elif value.get("allow_all_outbounds"):
            rule["outbound_allow_list"] = [{"peer_specification_type": "ALL"}]
        if value.get("policy_mode"):
            rule["action"] = value["policy_mode"]
        return rule

    def _generate_bound_spec(self, payload, list_of_rules):
        for rule in list_of_rules:
            if rule.get("rule_id"):
                rule_spec = self._filter_by_uuid(rule["rule_id"], payload)
                if rule.get("state") == "absent":
                    payload.remove(rule_spec)
                    continue
            else:
                rule_spec = {}
            if rule.get("categories"):
                rule_spec["filter"] = self._get_default_filter_spec()
                rule_spec["filter"]["params"] = rule["categories"]
                rule_spec["peer_specification_type"] = "FILTER"
            elif rule.get("ip_subnet"):
                rule_spec["ip_subnet"] = rule["ip_subnet"]
                rule_spec["peer_specification_type"] = "IP_SUBNET"
            elif rule.get("address"):
                address_group = rule["address"]

                if address_group.get("uuid"):
                    address_group["kind"] = "address_group"
                    rule_spec["address_group_inclusion_list"] = [address_group]
                elif address_group.get("name"):
                    ag = AddressGroup(self.session)
                    uuid = ag.get_uuid_by_name(address_group["name"])

                    if not uuid:
                        raise Exception(f"Cannot find the Address Group {address_group['name']}!")

                    address_group["kind"] = "address_group"
                    address_group["uuid"] = uuid
                    rule_spec["address_group_inclusion_list"] = [address_group]

                    rule_spec["peer_specification_type"] = "IP_SUBNET"

            if rule.get("protocol"):
                self._generate_protocol_spec(rule_spec, rule["protocol"])
            if rule.get("description"):
                rule_spec["description"] = rule["description"]
            if not rule_spec.get("rule_id"):
                payload.append(rule_spec)
        return payload

    def _generate_protocol_spec(self, payload, config):
        if config.get("tcp"):
            payload["protocol"] = "TCP"
            payload["tcp_port_range_list"] = config["tcp"]
        elif config.get("udp"):
            payload["protocol"] = "UDP"
            payload["udp_port_range_list"] = config["udp"]
        elif config.get("icmp"):
            payload["protocol"] = "ICMP"
            payload["icmp_type_code_list"] = config["icmp"]
        elif config.get("service"):
            service = config["service"]

            if service.get("uuid"):
                service["kind"] = "service_group"
                payload["service_group_list"] = [service]
            elif service.get("name"):
                sg = ServiceGroup(self.session)
                uuid = sg.get_uuid_by_name(service["name"])

                if not uuid:
                    raise Exception(f"Cannot find the Address Group {service['name']}!")

                service["kind"] = "service_group"
                service["uuid"] = uuid
                payload["service_group_list"] = [service]

    @staticmethod
    def _get_default_filter_spec():
        return deepcopy(
            {"type": "CATEGORIES_MATCH_ALL", "kind_list": ["vm"], "params": {}}
        )

    @staticmethod
    def _filter_by_uuid(uuid, items_list):
        try:
            return next(filter(lambda d: d.get("rule_id") == uuid, items_list))
        except Exception as e:
            raise e
