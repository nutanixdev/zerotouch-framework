from copy import deepcopy
from helpers.general_utils import convert_to_secs
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pc_entity import PcEntity
from helpers.log_utils import get_logger
from scripts.python.helpers.v3.availabilty_zone import AvailabilityZone

logger = get_logger(__name__)


class ProtectionRule(PcEntity):
    kind = "protection_rule"

    def __init__(self, session: RestAPIUtil):
        self.remote_pe_clusters = self.source_pe_clusters = None
        self.resource_type = "/protection_rules"
        super(ProtectionRule, self).__init__(session)
        self.build_spec_methods = {
            "name": self._build_spec_name,
            "desc": self._build_spec_desc,
            "start_time": self._build_spec_start_time,
            "protected_categories": self._build_spec_protected_categories,
            "schedules": self._build_spec_schedules,
        }

    def get_payload(self, pr_spec: dict, source_pe_clusters: dict, remote_pe_clusters: dict):
        """
        Payload for creating a Protection Rule
        """
        self.source_pe_clusters = source_pe_clusters
        self.remote_pe_clusters = remote_pe_clusters
        spec, error = super(ProtectionRule, self).get_spec(params=pr_spec)
        if error:
            raise Exception("Failed generating protection-rule spec: {}".format(error))

        return spec

    @staticmethod
    def _get_default_spec():
        return deepcopy(
            {
                "metadata": {"kind": "protection_rule"},
                "spec": {
                    "resources": {
                        "availability_zone_connectivity_list": [],
                        "ordered_availability_zone_list": [],
                        "category_filter": {
                            "params": {},
                            "type": "CATEGORIES_MATCH_ANY",
                        },
                        "primary_location_list": [],
                    },
                    "name": None,
                },
            }
        )

    @staticmethod
    def _build_spec_name(payload, name):
        payload["spec"]["name"] = name
        return payload, None

    @staticmethod
    def _build_spec_desc(payload, desc):
        payload["spec"]["description"] = desc
        return payload, None

    @staticmethod
    def _build_spec_start_time(payload, start_time):
        payload["spec"]["resources"]["start_time"] = start_time
        return payload, None

    @staticmethod
    def _build_spec_protected_categories(payload, categories):
        payload["spec"]["resources"]["category_filter"]["params"] = categories
        return payload, None

    def _build_spec_schedules(self, payload, schedules):
        ordered_az_list = []
        az_connectivity_list = []

        payload["spec"]["resources"]["primary_location_list"] = [0]

        # create ordered_availability_zone_list
        for schedule in schedules:
            if schedule.get("source") and schedule["source"] not in ordered_az_list:
                if schedule["source"].get("availability_zone"):
                    az_pc = AvailabilityZone(self.session)
                    schedule["source"]["availability_zone_url"] = az_pc.get_mgmt_url_by_name("Local AZ")
                else:
                    raise Exception("Unknown AZ specified in the schedule!")
                if schedule["source"].get("cluster") and schedule["source"].get("availability_zone"):
                    cluster = schedule["source"].pop("cluster")
                    pc_ip = schedule["source"].pop("availability_zone")
                    schedule["source"]["cluster_uuid"] = self.source_pe_clusters[pc_ip][cluster]
                else:
                    raise Exception("Unknown cluster specified in the schedule!")
                ordered_az_list.append(schedule["source"])

            if schedule.get("destination") and schedule["destination"] not in ordered_az_list:
                if schedule["destination"].get("availability_zone"):
                    az_pc = AvailabilityZone(self.session)
                    schedule["destination"]["availability_zone_url"] = az_pc.get_mgmt_url_by_name(
                        f"PC_{schedule['destination']['availability_zone']}")
                else:
                    raise Exception("Unknown AZ specified in the schedule!")

                if schedule["destination"].get("cluster") and schedule["destination"].get("availability_zone"):
                    cluster = schedule["destination"].pop("cluster")
                    pc_ip = schedule["destination"].pop("availability_zone")
                    schedule["destination"]["cluster_uuid"] = self.remote_pe_clusters[pc_ip][cluster]
                else:
                    raise Exception("Unknown cluster specified in the schedule!")
                ordered_az_list.append(schedule["destination"])
        payload["spec"]["resources"]["ordered_availability_zone_list"] = ordered_az_list

        # create availability_zone_connectivity_list from schedules
        az_conn_list = [
            {
                "source_availability_zone_index": 0,
                "destination_availability_zone_index": 1,
                "snapshot_schedule_list": []
            },
            {
                "source_availability_zone_index": 1,
                "destination_availability_zone_index": 0,
                "snapshot_schedule_list": []
            }
        ]
        for schedule in schedules:
            spec = {}
            az_connection_spec = deepcopy(az_conn_list)

            if schedule["protection_type"] == "ASYNC":
                if (
                    not (schedule.get("rpo") and schedule.get("rpo_unit"))
                    and schedule.get("snapshot_type")
                    and (schedule.get("local_retention_policy") or schedule.get("remote_retention_policy")
                )
                ):
                    return (
                        None,
                        "rpo, rpo_unit, snapshot_type and atleast one policy are required fields for "
                        "asynchronous snapshot schedule",
                    )

                spec["recovery_point_objective_secs"], err = convert_to_secs(
                    schedule["rpo"], schedule["rpo_unit"]
                )
                if err:
                    return None, err

                spec["snapshot_type"] = schedule["snapshot_type"]
                if schedule.get("local_retention_policy"):
                    spec["local_snapshot_retention_policy"] = schedule[
                        "local_retention_policy"
                    ]
                if schedule.get("remote_retention_policy"):
                    spec["remote_snapshot_retention_policy"] = schedule[
                        "remote_retention_policy"
                    ]
            else:
                if schedule.get("auto_suspend_timeout"):
                    spec["auto_suspend_timeout_secs"] = schedule["auto_suspend_timeout"]
                spec["recovery_point_objective_secs"] = 0

            az_connection_spec[0]["snapshot_schedule_list"] = [spec]
            az_connection_spec[1]["snapshot_schedule_list"] = [spec]
            az_connectivity_list.extend(az_connection_spec)

        payload["spec"]["resources"][
            "availability_zone_connectivity_list"
        ] = az_connectivity_list
        return payload, None
