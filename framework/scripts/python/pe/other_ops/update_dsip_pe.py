from typing import Dict
from framework.scripts.python.helpers.v2.cluster import Cluster as PeCluster
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class UpdateDsip(ClusterScript):
    """
    Update DSIP for the input PE clusters
    """
    def __init__(self, data: Dict, **kwargs):
        super(UpdateDsip, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        if not cluster_details.get("dsip"):
            self.logger.warning(f"DSIP is not passed in '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                                f" Skipping...'")
            return

        pe_session = cluster_details["pe_session"]
        cluster = PeCluster(pe_session)
        cluster.get_cluster_info()
        cluster_details["cluster_info"].update(cluster.cluster_info)
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        current_dsip = cluster_details.get("cluster_info", {}).get("cluster_external_data_services_ipaddress")
        if current_dsip:
            self.logger.warning(f"Data services IP is already set to {current_dsip} in {cluster_info!r}")
            return

        # Check if dsip is "get-ip-from-ipam" to fetch DSIP IP from IPAM and create host record in IPAM
        #       If Host record already exists for the FQDN, exisiting IP for that host record will be fetched
        if cluster_details.get("dsip") == "get-ip-from-ipam":
            if not self.data.get("ipam_network"):
                self.logger.warning("Network details 'ipam_network' not provided to fetch IP from IPAM subnet for "
                                    f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
                return
            if not self.data.get("ipam_session"):
                self.logger.warning("Kindly verify if 'ipam' configuration exists in 'global.yml' to get Data Services IP from IPAM"
                                    f" for '{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
                return
            fqdn = f"{cluster_details['cluster_info']['name']}-dsip.{self.data['ipam_network']['domain']}"
            ip, error = self.data["ipam_session"].create_host_record_with_next_available_ip(network=self.data["ipam_network"]["subnet"],
                                                                                            fqdn=fqdn)
            if error:
                self.exceptions.append(f"Failed to fetch DSIP IP from IPAM for '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                                       f" Error: {error}")
                return
            self.logger.info(f"Created Host record {fqdn} for next available IP {ip}")
            cluster_details["dsip"] = ip
        # If not dsip "get-ip-from-ipam", check if ipam_session is available to create host record for the given IP
        #       Skip if host record already exists for the given IP
        elif self.data.get("ipam_session"):
            if self.data["ipam_session"].check_host_record_exists(ip=cluster_details["dsip"]):
                self.logger.warning(f"Host record present for given IP {cluster_details['dsip']}. Skipping host record creation")
            else:
                fqdn = f"{cluster_details['cluster_info']['name']}-dsip.{self.data['ipam_network']['domain']}"
                ip, error = self.data["ipam_session"].create_host_record(fqdn=fqdn, ip=cluster_details["dsip"])
                if error:
                    self.exceptions.append(f"Failed to create host record for DSIP IP from IPAM for '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                                           f" Error: {error}")
                    return

        try:
            self.logger.info(f"Updating DSIP in {cluster_info!r}")
            response = cluster.update_dsip(cluster_details["dsip"])

            if response.get("value"):
                self.logger.info(f"Updated cluster DSIP to {cluster_details['dsip']} in {cluster_info!r}")
            else:
                self.exceptions.append(f"Failed to update cluster DSIP in {cluster_info!r}")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info!r} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if DSIP was updated
        try:
            if not cluster_details.get("dsip"):
                return

            self.results["clusters"][cluster_ip] = {
                "Update_DSIP": "CAN'T VERIFY"
            }

            pe_session = cluster_details["pe_session"]
            cluster = PeCluster(pe_session)
            cluster.get_cluster_info()
            cluster_details["cluster_info"].update(cluster.cluster_info)

            dsip = cluster_details.get("cluster_info", {}).get("cluster_external_data_services_ipaddress")
            if dsip:
                self.results["clusters"][cluster_ip]["Update_DSIP"] = "PASS"
            else:
                self.results["clusters"][cluster_ip]["Update_DSIP"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(
                f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}")
