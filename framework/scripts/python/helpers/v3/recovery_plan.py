from copy import deepcopy
from typing import List, Dict, Optional
from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity_v3 import PcEntity
from ..v3.availabilty_zone import AvailabilityZone
from ..v3.vm import VM


class RecoveryPlan(PcEntity):
    kind = "recovery_plan"

    def __init__(self, session: RestAPIUtil):
        self.source_pe_clusters = self.primary_location_cluster_list = self.recovery_location_cluster_list = \
            self.primary_location_url = self.recovery_location_url = self.remote_pe_clusters = None
        self.resource_type = "/recovery_plans"
        super(RecoveryPlan, self).__init__(session)
        self.build_spec_methods = {
            "name": self._build_spec_name,
            "desc": self._build_spec_desc,
            "primary_location": self._build_spec_primary_location,
            "recovery_location": self._build_spec_recovery_location,
            "stages": self._build_spec_stages,
            "network_mappings": self._build_spec_network_mappings,
            "floating_ip_assignments": self._build_spec_floating_ip_assignments,
        }

    def get_payload(self, rp_spec: Dict, source_pe_clusters: Dict, remote_pe_clusters: Dict) -> Dict:
        """
        Payload for creating a Recovery plan
        """
        self.source_pe_clusters = source_pe_clusters
        spec, error = super(RecoveryPlan, self).get_spec(params=rp_spec)
        if error:
            raise Exception("Failed generating recovery-plan spec: {}".format(error))

        return spec

    def _get_default_spec(self):
        return deepcopy(
            {
                "api_version": "3.1.0",
                "metadata": {"kind": "recovery_plan"},
                "spec": {
                    "resources": {
                        "parameters": {
                            "network_mapping_list": [],
                            "floating_ip_assignment_list": [],
                            "availability_zone_list": [{}, {}],
                            "primary_location_index": 0,
                        },
                        "stage_list": [],
                    },
                    "name": None,
                },
            }
        )

    @staticmethod
    def _build_spec_name(payload: Dict, name: str, complete_config: Optional[Dict] = None) -> (Dict, None):
        payload["spec"]["name"] = name
        return payload, None

    @staticmethod
    def _build_spec_desc(payload: Dict, desc: str, complete_config: Optional[Dict] = None) -> (Dict, None):
        payload["spec"]["description"] = desc
        return payload, None

    def _build_spec_stages(self, payload: Dict, stages: List, complete_config: Optional[Dict] = None) -> (Dict, None):
        stage_list = []
        for stage in stages:
            stage_spec = {
                "stage_work": {"recover_entities": {"entity_info_list": None}}
            }

            # for each stage add all vms and categories
            stage_entities = []
            for vm in stage.get("vms", []):
                vm_ref, err = self.get_vm_reference_spec(vm)
                if err:
                    return None, err
                vm_spec = {"any_entity_reference": vm_ref}
                if vm.get("enable_script_exec"):
                    vm_spec["script_list"] = [
                        {"enable_script_exec": vm["enable_script_exec"]}
                    ]
                stage_entities.append(vm_spec)

            for category in stage.get("categories", []):
                category_spec = {"categories": {category["key"]: category["value"]}}
                if category.get("enable_script_exec"):
                    category_spec["script_list"] = [
                        {"enable_script_exec": category["enable_script_exec"]}
                    ]
                stage_entities.append(category_spec)

            stage_spec["stage_work"]["recover_entities"][
                "entity_info_list"
            ] = stage_entities

            if stage.get("delay"):
                stage_spec["delay_time_secs"] = stage["delay"]
            stage_list.append(stage_spec)

        payload["spec"]["resources"]["stage_list"] = stage_list
        return payload, None

    def _build_network_mapping_spec(self, config: Dict, network_type: str, are_network_stretched=False) -> Dict:
        ntw_spec = {}
        custom_ip_specs = []

        # set custom IP mappings for vms
        if config.get("custom_ip_config") and not are_network_stretched:
            for ip_config in config["custom_ip_config"]:
                vm_ref, err = self.get_vm_reference_spec(ip_config["vm"])
                if err:
                    raise err
                custom_ip_spec = {
                    "vm_reference": vm_ref,
                    "ip_config_list": [{"ip_address": ip_config["ip"]}],
                }
                custom_ip_specs.append(custom_ip_spec)

        # subnet related details for particular network
        subnet_spec = {}
        if config.get("gateway_ip"):
            subnet_spec["gateway_ip"] = config["gateway_ip"]
        if config.get("prefix"):
            subnet_spec["prefix_length"] = int(config["prefix"])
        if config.get("external_connectivity_state"):
            subnet_spec["external_connectivity_state"] = config[
                "external_connectivity_state"
            ]

        # add to respective network config as per test or prod network
        if network_type == "test":
            if custom_ip_specs:
                ntw_spec["test_ip_assignment_list"] = custom_ip_specs
            ntw_spec["test_network"] = {
                "name": config["name"],
            }
            if subnet_spec:
                ntw_spec["test_network"]["subnet_list"] = [subnet_spec]

        else:
            if custom_ip_specs:
                ntw_spec["recovery_ip_assignment_list"] = custom_ip_specs
            ntw_spec["recovery_network"] = {
                "name": config["name"],
            }
            if subnet_spec:
                ntw_spec["recovery_network"]["subnet_list"] = [subnet_spec]

        return ntw_spec

    def _build_spec_network_mappings(self, payload: Dict, network_mappings: List,
                                     complete_config: Optional[Dict] = None) -> (Dict, None):

        # set flag to apply these settings to all network mappings
        are_network_stretched = False
        if complete_config.get("network_type") == "STRETCH":
            are_network_stretched = True

        # create primary and recovery location spec to be used in each network mappings
        if self.primary_location_url:
            primary_location = {
                "availability_zone_url": self.primary_location_url
            }
            if self.primary_location_cluster_list:
                primary_location["cluster_reference_list"] = self.primary_location_cluster_list
        else:
            primary_location_index = payload["spec"]["resources"]["parameters"][
                "primary_location_index"
            ]
            primary_location = payload["spec"]["resources"]["parameters"][
                "availability_zone_list"
            ][primary_location_index]

        if self.recovery_location_url:
            recovery_location = {
                "availability_zone_url": self.recovery_location_url
            }
            if self.recovery_location_cluster_list:
                recovery_location["cluster_reference_list"] = self.recovery_location_cluster_list
        else:
            recovery_location_index = (
                payload["spec"]["resources"]["parameters"]["primary_location_index"] ^ 1
            )
            recovery_location = payload["spec"]["resources"]["parameters"][
                "availability_zone_list"
            ][recovery_location_index]

        network_mapping_specs = []
        for ntw in network_mappings:
            spec = {}

            # add primary and recovery site networks each having test and production(also called recovery networks)
            primary_site_ntw_spec = {}
            recovery_site_ntw_spec = {}
            if ntw["primary"].get("test"):
                primary_site_ntw_spec.update(
                    self._build_network_mapping_spec(
                        ntw["primary"]["test"], "test", are_network_stretched
                    )
                )

            if ntw["primary"].get("prod"):
                primary_site_ntw_spec.update(
                    self._build_network_mapping_spec(
                        ntw["primary"]["prod"], "prod", are_network_stretched
                    )
                )

            if ntw["recovery"].get("test"):
                recovery_site_ntw_spec.update(
                    self._build_network_mapping_spec(
                        ntw["recovery"]["test"], "test", are_network_stretched
                    )
                )

            if ntw["recovery"].get("prod"):
                recovery_site_ntw_spec.update(
                    self._build_network_mapping_spec(
                        ntw["recovery"]["prod"], "prod", are_network_stretched
                    )
                )

            primary_site_ntw_spec.update(primary_location)
            recovery_site_ntw_spec.update(recovery_location)

            spec["are_networks_stretched"] = are_network_stretched
            spec["availability_zone_network_mapping_list"] = [
                primary_site_ntw_spec,
                recovery_site_ntw_spec,
            ]
            network_mapping_specs.append(spec)

        payload["spec"]["resources"]["parameters"][
            "network_mapping_list"
        ] = network_mapping_specs
        return payload, None

    def _build_spec_primary_location(self, payload: Dict, primary_location: Dict,
                                     complete_config: Optional[Dict] = None) -> (Dict, None):
        primary_location_index = payload["spec"]["resources"]["parameters"][
            "primary_location_index"
        ]

        az_pc = AvailabilityZone(self.session)
        self.primary_location_url = primary_location["url"] = az_pc.get_mgmt_url_by_name("Local AZ")

        spec = {"availability_zone_url": primary_location["url"]}

        # cluster is only specified if it is Local_AZ to Local_AZ
        if primary_location.get("cluster"):
            cluster = primary_location["cluster"]
            pc_ip = primary_location["availability_zone"]
            if cluster not in self.source_pe_clusters.get(pc_ip, {}):
                raise Exception("Unknown AZ or cluster specified in the schedule!")
            cluster_uuid = self.source_pe_clusters[pc_ip][cluster]
            self.primary_location_cluster_list = spec["cluster_reference_list"] = [
                {
                    "kind": "cluster",
                    "uuid": cluster_uuid
                }
            ]

        payload["spec"]["resources"]["parameters"]["availability_zone_list"][
            primary_location_index
        ] = spec
        return payload, None

    def _build_spec_recovery_location(self, payload, recovery_location: Dict,
                                      complete_config: Optional[Dict] = None) -> (Dict, None):
        recovery_location_index = (
            payload["spec"]["resources"]["parameters"]["primary_location_index"] ^ 1
        )

        if recovery_location.get("availability_zone"):
            az_pc = AvailabilityZone(self.session)
            if (recovery_location['availability_zone'] ==
               complete_config.get("primary_location", {}).get("availability_zone")):
                self.recovery_location_url = recovery_location["url"] = az_pc.get_mgmt_url_by_name("Local AZ")
            else:
                self.recovery_location_url = recovery_location["url"] = \
                    az_pc.get_mgmt_url_by_name(f"PC_{recovery_location['availability_zone']}")
        else:
            raise Exception("AZ not specified in the recovery location!")

        spec = {"availability_zone_url": recovery_location["url"]}

        # cluster is only specified if it is Local_AZ to Local_AZ
        if recovery_location.get("cluster"):
            cluster = recovery_location.get("cluster")
            pc_ip = recovery_location.get("availability_zone")
            cluster_uuid = self.source_pe_clusters[pc_ip][cluster]
            self.recovery_location_cluster_list = spec["cluster_reference_list"] = [
                {
                    "kind": "cluster",
                    "uuid": cluster_uuid
                }
            ]

        payload["spec"]["resources"]["parameters"]["availability_zone_list"][
            recovery_location_index
        ] = spec
        return payload, None

    def _build_spec_floating_ip_assignments(self, payload: Dict, floating_ip_assignments: List,
                                            complete_config: Optional[Dict] = None) -> (Dict, None):
        floating_ip_assignment_specs = []
        for config in floating_ip_assignments:
            floating_ip_assignment_spec = {"availability_zone_url": config[
                "availability_zone_url"
            ]}
            vm_ip_assignment_specs = []
            for ip_spec in config["vm_ip_assignments"]:
                ip_assignment_spec = {}

                # add vm reference
                vm_ref, err = self.get_vm_reference_spec(ip_spec["vm"])
                if err:
                    return None, err
                ip_assignment_spec["vm_reference"] = vm_ref

                # add nic info
                ip_assignment_spec["vm_nic_information"] = {
                    "uuid": ip_spec["vm_nic_info"]["uuid"]
                }
                if ip_spec["vm_nic_info"].get("ip"):
                    ip_assignment_spec["vm_nic_information"]["ip"] = ip_spec[
                        "vm_nic_info"
                    ]["ip"]

                # test floating ip config
                if ip_spec.get("test_ip_config"):
                    ip_assignment_spec["test_floating_ip_config"] = {
                        "ip": ip_spec["test_ip_config"]["ip"]
                    }
                    if ip_spec["test_ip_config"].get("allocate_dynamically"):
                        ip_assignment_spec["test_floating_ip_config"][
                            "should_allocate_dynamically"
                        ] = ip_spec["test_ip_config"]["allocate_dynamically"]

                # recovery floating ip config
                if ip_spec.get("prod_ip_config"):
                    ip_assignment_spec["recovery_floating_ip_config"] = {
                        "ip": ip_spec["prod_ip_config"]["ip"]
                    }
                    if ip_spec["prod_ip_config"].get("allocate_dynamically"):
                        ip_assignment_spec["recovery_floating_ip_config"][
                            "should_allocate_dynamically"
                        ] = ip_spec["prod_ip_config"]["allocate_dynamically"]

                vm_ip_assignment_specs.append(ip_assignment_spec)

            floating_ip_assignment_spec[
                "vm_ip_assignment_list"
            ] = vm_ip_assignment_specs
            floating_ip_assignment_specs.append(floating_ip_assignment_spec)

        payload["spec"]["resources"]["parameters"][
            "floating_ip_assignment_list"
        ] = floating_ip_assignment_specs
        return payload, None

    def get_vm_reference_spec(self, vm_config: Dict) -> (Dict, None):
        uuid = vm_config.get("uuid", "")
        name = vm_config.get("name", "")
        if ("name" not in vm_config) and ("uuid" not in vm_config):
            return None, "Provide name or uuid for building vm reference spec"
        elif "name" not in vm_config:
            vm = VM(self.session)
            resp = vm.read(vm_config["uuid"])
            name = resp["status"]["name"]
        elif "uuid" not in vm_config:
            vm = VM(self.session)
            # pass cluster info
            uuid = vm.get_uuid_by_name(vm_config.get("name"))
            if not uuid:
                error = f"VM {0} not found.".format(name)
                return Exception(error)

        vm_ref_spec = {"kind": "vm", "name": name, "uuid": uuid}
        return vm_ref_spec, None
