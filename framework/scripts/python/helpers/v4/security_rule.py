from copy import deepcopy
from framework.helpers.v4_api_client import ApiClientV4
from ..pc_batch_op_v4 import PcBatchOpv4
from .category import Category
from .address_group import AddressGroup
from .service_group import ServiceGroup

import ntnx_microseg_py_client
import ntnx_microseg_py_client.models.microseg.v4.config as v4MicrosegConfig

class SecurityPolicy:
    # Configure the client
    def __init__(self, v4_api_util: ApiClientV4):
        self.resource_type = "microseg/v4.0/config/policies"
        self.kind = "SecurityPolicy"
        self.client = v4_api_util.get_api_client("microseg")
        self.network_security_policies_api = ntnx_microseg_py_client.NetworkSecurityPoliciesApi(
            api_client=self.client
            )
        self.batch_op = PcBatchOpv4(v4_api_util, resource_type=self.resource_type, kind=self.kind)
        self.category = Category(v4_api_util)
        self.address_group = AddressGroup(v4_api_util)
        self.service_group = ServiceGroup(v4_api_util)
    
    def list(self):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        all_entities = []
        page = 0
        while True:
            response = self.network_security_policies_api.list_network_security_policies(
                _page=page, _limit=50, **headers)
            if not response.data:
                break  # Exit the loop if there are no more entities to fetch
            all_entities.extend(response.data)
            page += 1  # Move to the next page to fetch more entities
        # We use this loop to ensure all entities are retrieved across multiple pages,
        # as the API returns a limited number of records per request.
        
        return all_entities

    def get_name_list(self):
        return [sp.name for sp in self.list()]

    def get_name_uuid_dict(self):
        return {sp.name: sp.ext_id for sp in self.list()}
    
    def get_by_ext_id(self, ext_id):
        return self.network_security_policies_api.get_network_security_policy_by_id(ext_id)

    def create_security_policy_spec(self, sp_info):

        networkSecurityPolicy = v4MicrosegConfig.NetworkSecurityPolicy.NetworkSecurityPolicy()

        # NetworkSecurityPolicy object initializations here...
        networkSecurityPolicy.name = sp_info['name']
        
        networkSecurityPolicy.type = getattr(v4MicrosegConfig.SecurityPolicyType.SecurityPolicyType, sp_info["type"])
        if sp_info.get("description"):
            networkSecurityPolicy.description = sp_info["description"]
        if sp_info.get("allow_ipv6_traffic"):
            networkSecurityPolicy.allow_ipv6_traffic = sp_info.get("allow_ipv6_traffic", False)
        networkSecurityPolicy.isHitlogEnabled = sp_info.get("hitlog", True)
        if sp_info.get("policy_mode"):
            networkSecurityPolicy.state = getattr(v4MicrosegConfig.SecurityPolicyState.SecurityPolicyState,sp_info["policy_mode"])
        networkSecurityPolicy.rules = []
        if sp_info.get("app_rule"):
            for rule in sp_info["app_rule"]:
                networkSecurityPolicy.rules.append(self.add_app_rule(rule))
                if rule["target_group"]["intra_group"]:
                    networkSecurityPolicy.rules.append(self.add_intra_group_rule(rule, True))
                else:
                    networkSecurityPolicy.rules.append(self.add_intra_group_rule(rule, False))
        if sp_info.get("two_env_isolation_rule"):
                networkSecurityPolicy.rules.append(self.add_env_isolation_rule(sp_info["two_env_isolation_rule"]))

        return networkSecurityPolicy

    def update_security_policy_spec(self, sp_info, sp_obj):
        if sp_info.get("new_name"):
            sp_obj.name = sp_info["new_name"]
        if sp_info.get("description"):
            sp_obj.description = sp_info["description"]
        if sp_info.get("allow_ipv6_traffic"):
            sp_obj.allow_ipv6_traffic = sp_info["allow_ipv6_traffic"]
        if sp_info.get("hitlog"):
            sp_obj.isHitlogEnabled = sp_info["hitlog"]
        if sp_info.get("policy_mode"):
            sp_obj.state = getattr(v4MicrosegConfig.SecurityPolicyState.SecurityPolicyState,sp_info["policy_mode"])
        if sp_info.get("app_rule"):
            sp_obj.rules = []
            for rule in sp_info["app_rule"]:
                sp_obj.rules.append(self.add_rule(rule))
        etag = self.client.get_etag(sp_obj)

        return sp_obj, etag

    def delete_security_policy_spec(self, ext_id):
        sp_obj = self.get_by_ext_id(ext_id)
        etag = self.client.get_etag(sp_obj.data)
        return sp_obj.data.ext_id, etag  

    def add_app_rule(self, rule):
        
        app_rule = v4MicrosegConfig.NetworkSecurityPolicyRule.NetworkSecurityPolicyRule()
        if rule.get("description"):
            app_rule.description = rule["description"]
        app_rule.spec = v4MicrosegConfig.ApplicationRuleSpec.ApplicationRuleSpec()
        app_rule.type = v4MicrosegConfig.RuleType.RuleType.APPLICATION
        app_rule.spec.secured_group_category_references = [
                    self.category.get_category_ext_id(category_type, value) 
                    for cg in rule["target_group"]["categories"] for category_type, value in cg.items()
                    ]

        if rule.get("inbounds"):
            inbound_rule = rule["inbounds"]
            if inbound_rule.get("allow_all"):
                app_rule.spec.src_allow_spec = v4MicrosegConfig.AllowType.AllowType.ALL
            elif inbound_rule.get("allow_none"):
                app_rule.spec.src_allow_spec = v4MicrosegConfig.AllowType.AllowType.NONE
            if inbound_rule.get("categories"):
                app_rule.spec.src_category_references = [
                        self.category.get_category_ext_id(category_type, value) 
                        for cg in inbound_rule["categories"] for category_type, value in cg.items()
                        ]
            if inbound_rule.get("address"):
                app_rule.spec.src_address_group_references = [
                    self.address_group.get_uuid_by_name(address["name"]) for address in inbound_rule["address"]
                    ]
            if inbound_rule.get("subnet"):
                app_rule.spec.src_subnet = ntnx_microseg_py_client.models.common.v1.config.IPv4Address.IPv4Address()
                value, prefix = inbound_rule["subnet"].split('/')
                app_rule.spec.src_subnet.value = value
                app_rule.spec.src_subnet.prefix_length = prefix

        elif rule.get("outbounds"):
            outbound_rule = rule["outbounds"]
            if outbound_rule.get("allow_all"):
                app_rule.spec.dest_allow_spec = v4MicrosegConfig.AllowType.AllowType.ALL
            elif outbound_rule.get("allow_none"):
                app_rule.spec.dest_allow_spec = v4MicrosegConfig.AllowType.AllowType.NONE

            if outbound_rule.get("categories"):
                app_rule.spec.dest_category_references = [
                        self.category.get_category_ext_id(category_type, value) 
                        for cg in outbound_rule["categories"] for category_type, value in cg.items()
                        ]
            if outbound_rule.get("address"):
                app_rule.spec.dest_address_group_references = [
                    self.address_group.get_uuid_by_name(address["name"]) for address in outbound_rule["address"]
                    ]
            if outbound_rule.get("subnet"):
                app_rule.spec.src_subnet = ntnx_microseg_py_client.models.common.v1.config.IPv4Address.IPv4Address()
                value, prefix = outbound_rule["subnet"].split('/')
                app_rule.spec.src_subnet.value = value
                app_rule.spec.src_subnet.prefix_length = int(prefix)

        if rule.get("services"):
            service_config = rule["services"]
            if service_config.get("all"):
                    app_rule.spec.is_all_protocol_allowed = True
            else:
                if service_config.get("tcp"):
                    app_rule.spec.tcp_services = []
                    for tcp in service_config["tcp"]:
                        tcp_port_range = v4MicrosegConfig.TcpPortRangeSpec.TcpPortRangeSpec()
                        tcp_port_range.start_port = tcp["start_port"]
                        tcp_port_range.end_port = tcp["end_port"]
                        app_rule.spec.tcp_services.append(tcp_port_range)

                if service_config.get("udp"):
                    app_rule.spec.udp_services = []
                    for udp in service_config["udp"]:
                        udp_port_range = v4MicrosegConfig.UdpPortRangeSpec.UdpPortRangeSpec()
                        udp_port_range.start_port = udp["start_port"]
                        udp_port_range.end_port = udp["end_port"]
                        app_rule.spec.udp_services.append(udp_port_range)

                if service_config.get("icmp"):
                    app_rule.spec.icmp_services = []
                    for icmp in service_config["icmp"]:
                        icmp_type_code = v4MicrosegConfig.IcmpTypeCodeSpec.IcmpTypeCodeSpec()
                        if icmp.get("type") == "Any" and icmp.get("code") == "Any":
                            icmp_type_code.is_all_allowed = True
                        else:
                            if not icmp.get("type") == "Any":
                                # Ignore the field if it is "Any"
                                icmp_type_code.type = icmp["type"]
                            if not icmp.get("code") == "Any":
                                # Ignore the field if it is "Any"
                                icmp_type_code.code = icmp["code"]
                        app_rule.spec.icmp_services.append(icmp_type_code)

                if service_config.get("service_group"):
                    app_rule.spec.service_group_references = [
                        self.service_group.get_uuid_by_name(address["name"]) for address in service_config["service_group"]
                        ]
        return app_rule

    def add_intra_group_rule(self, rule, action):
        app_rule = v4MicrosegConfig.NetworkSecurityPolicyRule.NetworkSecurityPolicyRule()
        app_rule.type = v4MicrosegConfig.RuleType.RuleType.INTRA_GROUP
        app_rule.spec = v4MicrosegConfig.IntraEntityGroupRuleSpec.IntraEntityGroupRuleSpec()

        app_rule.spec.secured_group_category_references = [
            self.category.get_category_ext_id(type, value) 
            for cg in rule["target_group"]["categories"] for type, value in cg.items()
        ]
        if action:
            app_rule.spec.secured_group_action = v4MicrosegConfig.IntraEntityGroupRuleAction.IntraEntityGroupRuleAction.ALLOW
        else:
            app_rule.spec.secured_group_action = v4MicrosegConfig.IntraEntityGroupRuleAction.IntraEntityGroupRuleAction.DENY
        return app_rule 

    def add_env_isolation_rule(self, rule):
        isolation_rule = v4MicrosegConfig.NetworkSecurityPolicyRule.NetworkSecurityPolicyRule()
        
        isolation_rule.spec = v4MicrosegConfig.TwoEnvIsolationRuleSpec.TwoEnvIsolationRuleSpec()
        isolation_rule.type = v4MicrosegConfig.RuleType.RuleType.TWO_ENV_ISOLATION
        isolation_rule.spec.first_isolation_group = [
            self.category.get_category_ext_id(category_type, value) 
                for cg in rule["first_isolation_group"]
                    for category_type, value in cg.items()
            ]
        isolation_rule.spec.second_isolation_group = [
            self.category.get_category_ext_id(category_type, value) 
                for cg in rule["second_isolation_group"]
                    for category_type, value in cg.items()
            ]
        return isolation_rule