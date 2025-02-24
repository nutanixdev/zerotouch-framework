import traceback
from copy import deepcopy
from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.ndb.operations import Operation
from framework.scripts.python.helpers.ndb.profiles import Profile
from framework.scripts.python.helpers.ndb.settings import Setting
from framework.scripts.python.helpers.state_monitor.ndb_task_monitor import NdbTaskMonitor
from framework.scripts.python.helpers.state_monitor.ndb_upload_json_monitor import NdbUploadJsonMonitor
from framework.scripts.python.helpers.state_monitor.ndb_vip_monitor import NdbVipMonitor
from framework.scripts.python.pe.upload.upload_image import UploadImagePe
from framework.scripts.python.pe.create.create_vm_pe import CreateVmPe
from framework.scripts.python.pe.other_ops.power_transition_vm_pe import PowerTransitionVmPe
from framework.scripts.python.helpers.batch_script import BatchScript
from framework.scripts.python.helpers.ndb.auth import Auth
from framework.scripts.python.helpers.ndb.clusters import Cluster
from framework.scripts.python.helpers.ndb.config import Config
from framework.scripts.python.helpers.ndb.resources import Resource
from framework.scripts.python.helpers.v1.vm import VM
from framework.scripts.python.script import Script
from framework.helpers.log_utils import get_logger
from framework.helpers.helper_functions import create_ndb_objects, read_creds, create_pe_objects

logger = get_logger(__name__)


class NdbConfig(Script):
    """
    Configure Ndb with below configs
    """

    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: Dict, **kwargs):
        self.ndb_ip = self.config_op = self.resource_op = self.cluster_op = self.ndb_session = self.setting_op = \
            self.profile_op = self.operation_op = None
        self.data = deepcopy(data)
        super(NdbConfig, self).__init__(**kwargs)
        self.default_ndb_password = self.data.get('default_ndb_password') or self.DEFAULT_SYSTEM_PASSWORD
        self.ndb_config = self.data.get("ndb")
        self.logger = self.logger or logger

    def execute(self):
        try:
            if not self.ndb_config:
                self.logger.warning("Ndb config details not found in the payload")
                return

            # Get NDB VM details
            deployment_config = self.ndb_config["deployment_cluster"]
            ndb_vm_name = deployment_config["ndb_vm_name"]

            # If we have to deploy NDB in the cluster, we need to add VM name in the payload as it is not present
            if deployment_config.get("ndb_vm_config"):
                deployment_config["ndb_vm_config"]["name"] = ndb_vm_name

            # Get NDB IP
            try:
                self.get_ndb_ip(deployment_config)
            except Exception as e:
                raise Exception(f"Could not fetch NDB VM IP from the cluster. Error: {e}")

            if self.ndb_config.get("register_clusters"):
                # Now that we have the NDB IP, lets create NDB session
                create_ndb_objects(self.ndb_config, global_data=self.data)
                # Assign NDB session
                self.ndb_session = self.ndb_config["ndb_session"]
                # Init all the NDB ops we are using here
                self.init_ndb_ops()

                for cluster in self.ndb_config["register_clusters"]:
                    # Get cluster creds
                    try:
                        if "pe_credential" not in cluster:
                            raise Exception("PE credential not found in the cluster details")

                        # get credentials from the payload
                        pe_username, pe_password = read_creds(data=self.data, credential=cluster['pe_credential'])

                        cluster["username"] = pe_username
                        cluster["password"] = pe_password
                    except Exception as e:
                        self.exceptions.append(f"Could not read the PE credentials from the payload. Error: {e}")
                        continue

                    # If no cluster is registered to NDB, register the first cluster as initial cluster
                    # if not self.cluster_op.list():
                    if cluster.get("initial_cluster"):
                        # Register the initial cluster
                        try:
                            self.logger.info(f"Registering the initial cluster {cluster['name']!r} in NDB...")
                            cluster_info = self.register_initial_cluster(deepcopy(cluster))
                            self.logger.info("Refreshing the network")
                            self.refresh_network()
                        except Exception as e:
                            self.exceptions.append(f"Could not register the initial cluster {cluster['name']!r} "
                                                   f"in NDB. Error: {e}")
                            continue
                        # Update DNS,NTP,TZ,SMTP
                        try:
                            cluster_id = cluster_info.get("id")
                            self.logger.info(f"Updating the cluster services...")
                            self.update_cluster_services(cluster_id)
                        except Exception as e:
                            self.exceptions.append(f"Could not update the cluster services in {cluster['name']!r}."
                                                   f" Error: {e}")
                            continue
                        # Update storage container
                        try:
                            self.logger.info("Add Storage Container to the cluster...")
                            self.add_storage_container(deepcopy(cluster), cluster_id)
                        except Exception as e:
                            self.exceptions.append(f"Could not update the Storage Container details. Error: {e}")
                            continue
                        # Configure networks
                        try:
                            for dhcp_network in cluster.get("dhcp_networks"):
                                self.logger.info(f"Creating DHCP Network {dhcp_network!r}")
                                _ = self.resource_op.create_dhcp_network(cluster_id, dhcp_network)
                            # Get other static network params from cluster info
                            for name, static_network in cluster.get("static_networks", {}).items():
                                self.logger.info(f"Creating Static Network {name!r}")
                                # Get DNS and NTP details from cluster
                                response = self.config_op.get_cluster_config(cluster_id)
                                static_network["dns"] = response["dnsServers"][0]
                                _ = self.resource_op.create_static_network(cluster_id=cluster_id,
                                                                           network_name=name,
                                                                           default_gateway=static_network["gateway"],
                                                                           subnet_mask=static_network["netmask"],
                                                                           primary_dns=static_network["dns"],
                                                                           ip_ranges=static_network["ip_pools"])
                            self.logger.info("Refreshing the network...")
                            self.refresh_network()
                        except Exception as e:
                            self.exceptions.append(f"Could not create networks. Error: {e}")
                            continue
                        # Configure OOB Network Profiles
                        try:
                            self.logger.info("Creating OOB Network profiles...")
                            _ = self.profile_op.create_default_network_profiles(cluster["default_network_profile_vlan"])
                        except Exception as e:
                            self.exceptions.append(f"Could not create OOB Network profiles. Error: {e}")
                            continue
                        # Create Network profiles
                        try:
                            for network_profile in cluster.get("network_profiles", []):
                                self.logger.info(f"Creating Network profile {network_profile['name']!r}")
                                _ = self.profile_op.create_network_profile(
                                    name=network_profile["name"],
                                    vlan_name=network_profile["vlan"],
                                    engine=network_profile["engine"],
                                    cluster_id=cluster_id,
                                    description=network_profile.get("description"),
                                    topology=network_profile.get("topology"),
                                )
                        except Exception as e:
                            self.exceptions.append(f"Could not create Network profile. Error: {e}")
                            continue
                        # Wait for Software profiles to be configured
                        try:
                            self.logger.info("Waiting for NDB setup to complete...")
                            response = self.operation_op.get_operation_by_name(name="Configure OOB software profiles")
                            if response and response.get("id"):
                                response, status = NdbTaskMonitor(self.ndb_session, response["id"]).monitor()
                                if not status:
                                    raise Exception(f"NDB Task could not be completed in prescribed time. "
                                                    f"Response: {response}")
                                elif not response:
                                    raise Exception("Could not find the NDB Task to monitor")
                                else:
                                    self.logger.info("OOB software profiles configured successfully")
                            else:
                                self.logger.error("Could not configure OOB software profiles")
                        except Exception as e:
                            self.exceptions.append(f"Could not configure OOB software profiles. Error: {e}")
                        # If there are multiple clusters, enable multi-cluster
                        if len(self.ndb_config.get("register_clusters")) > 1:
                            try:
                                # Enable multi-cluster as there are multiple clusters
                                self.logger.info("Enabling Multi-cluster")
                                response = (
                                    self.cluster_op.enable_multicluster(vlan_name=cluster["agent_vm_vlan"]))
                                if response.get("operationId") and response.get("status") == "success":
                                    response, status = NdbTaskMonitor(self.ndb_session,
                                                                      task_id=response["operationId"]).monitor()
                                    if not status:
                                        raise Exception(f"NDB Task could not be completed in prescribed time. "
                                                        f"Response: {response}")
                                    elif not response:
                                        raise Exception("Could not find the NDB Task to monitor")
                                    else:
                                        self.logger.info("Multi-cluster enabled successfully")
                                else:
                                    raise Exception(response)
                            except Exception as e:
                                self.exceptions.append(f"Could not enable multi-cluster. Error: {e}")
                    else:
                        # Register a new cluster
                        try:
                            # Get DNS and NTP details from cluster
                            response = self.cluster_op.get_pe_cluster_info(cluster_name=cluster["name"],
                                                                           cluster_ip=cluster["cluster_ip"],
                                                                           username=cluster["username"],
                                                                           password=cluster["password"])
                            cluster["dns_servers"] = ",".join(response.get("dnsServers")) if response.get("dnsServers") else ""
                            cluster["ntp_servers"] = ",".join(response.get("ntpServers")) if response.get("ntpServers") else ""

                            self.logger.info(f"Registering New Cluster {cluster['name']}")
                            response = self.register_cluster(cluster)

                            if response.get("operationId") and response.get("status") == "success":
                                response, status = NdbTaskMonitor(self.ndb_session,
                                                                  task_id=response["operationId"]).monitor()
                                if not status:
                                    raise Exception(f"NDB Task to register new cluster could not be completed in "
                                                    f"prescribed time. Response: {response}")
                                elif not response:
                                    raise Exception("Could not find the NDB Task to monitor")
                                else:
                                    self.logger.info("New cluster registered successfully")
                            else:
                                raise Exception(response)
                        except Exception as e:
                            self.exceptions.append(f"Could not register new cluster in NDB. Error: {e}")

                # Perform generic operations
                if self.ndb_config.get("enable_pulse", None) is not None:
                    try:
                        self.logger.info("Update pulse")
                        _ = self.setting_op.set_pulse(True)
                    except Exception as e:
                        self.exceptions.append(f"Could not update the pulse. Error: {e}")

                # Create compute profiles
                for compute_profile in self.ndb_config.get("compute_profiles", []):
                    try:
                        self.logger.info(f"Creating Compute profile {compute_profile['name']!r}")
                        _ = self.profile_op.create_compute_profile(name=compute_profile["name"],
                                                                   description=compute_profile.get("description"),
                                                                   num_cpu=compute_profile.get("num_vcpus"),
                                                                   memory=compute_profile.get("memory_gib"),
                                                                   core_per_cpu=compute_profile.get("num_cores_per_vcpu"))
                    except Exception as e:
                        self.exceptions.append(f"Could not create Compute profile. Error: {e}")
        except Exception as e:
            tb_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
            self.exceptions.append(f"{type(self).__name__} failed for the NDB {self.ndb_ip!r} "
                                   f"with the error: {e} \n {tb_str}")

    def init_ndb_ops(self):
        self.cluster_op = Cluster(self.ndb_session)
        self.resource_op = Resource(self.ndb_session)
        self.setting_op = Setting(self.ndb_session)
        self.profile_op = Profile(self.ndb_session)
        self.config_op = Config(self.ndb_session)
        self.operation_op = Operation(self.ndb_session)

    def update_ndb_password(self, new_ndb_admin_credential: str):
        default_ndb_session = RestAPIUtil(self.ndb_ip,
                                          user=self.DEFAULT_USERNAME,
                                          pwd=self.default_ndb_password,
                                          secured=True)
        authn = Auth(default_ndb_session)

        # get credentials from the payload
        try:
            _, new_ndb_password = read_creds(data=self.data, credential=new_ndb_admin_credential)
        except Exception as e:
            raise Exception(f"Could not read the new NDB password from the payload. Error: {e}")

        if new_ndb_password == self.default_ndb_password:
            self.logger.error(f"New Password specified is same as default password for NDB...")
            return

        response = authn.update_password(new_password=new_ndb_password)
        if response.get("status"):
            self.logger.info(f"Default System password updated with new password in NDB")
        else:
            raise Exception(f"Could not change the NDB password. Error: {response}")

    def refresh_network(self):
        return self.resource_op.refresh_network()

    def update_cluster_services(self, cluster_id: str):
        ndb_config = self.config_op.get_cluster_config(cluster_id)
        ndb_config.pop("prismTimezone", "")

        self.logger.info("Updating DNS...")
        self.config_op.update_dns(ndb_config)

        self.logger.info("Updating NTP...")
        self.config_op.update_ntp(ndb_config)

        self.logger.info("Updating SMTP...")
        self.config_op.update_smtp(ndb_config)

        self.logger.info("Updating Timezone...")
        self.config_op.update_timezone(ndb_config)

    def register_initial_cluster(self, cluster_details: Dict):
        cluster_spec, error = self.cluster_op.get_new_cluster_spec(cluster_details)
        if error:
            raise Exception(error)

        response = self.cluster_op.create(data=cluster_spec)

        if "id" in response:
            self.logger.info(f"Initial Cluster registered successfully in NDB")

            self.logger.info("Uploading the cluster spec to the NDB")
            status, upload_response = NdbUploadJsonMonitor(self.ndb_session,
                                                           cluster_id=response["id"],
                                                           cluster_ip=cluster_details["cluster_ip"],
                                                           username=cluster_details["username"],
                                                           password=cluster_details["password"]).monitor()
            if not status:
                raise Exception(f"Could not upload the cluster spec to NDB. Error: {upload_response}")
            self.logger.info("Cluster spec uploaded successfully to NDB")

            return response
        else:
            raise Exception(f"Could not register the initial cluster in NDB. Error: {response}")

    def register_cluster(self, cluster_details: Dict):
        cluster_spec, error = self.cluster_op.get_cluster_spec(cluster_details)
        if error:
            raise Exception(error)

        return self.cluster_op.create(data=cluster_spec)

    def add_storage_container(self, cluster_details: dict, cluster_id: str):
        cluster_details["properties"] = [
            {
                "name": "ERA_STORAGE_CONTAINER",
                "value": cluster_details["storage_container"]
            }
        ]

        cluster_spec, error = self.cluster_op.get_update_cluster_spec(cluster_details)
        if error:
            raise Exception(error)

        response = self.cluster_op.update(data=cluster_spec, endpoint=cluster_id)

        if "id" in response:
            self.logger.info(f"Storage Container details updated successfully in NDB")

            self.logger.info("Uploading the cluster spec to the NDB")
            status, upload_response = NdbUploadJsonMonitor(self.ndb_session,
                                                           cluster_id=response["id"],
                                                           cluster_ip=cluster_details["cluster_ip"],
                                                           username=cluster_details["username"],
                                                           password=cluster_details["password"],
                                                           skip_upload="true",
                                                           skip_profile="false",
                                                           update_json="false").monitor()
            if not status:
                raise Exception(
                    f"Could not upload the cluster spec to NDB. Error: {upload_response}")
        else:
            raise Exception(
                f"Could not update the Storage Container details in NDB. Error: {response}")

    def get_ndb_ip(self, deployment_config: dict):
        """
        Get the NDB IP from PE. If vm is already present, get the IP from the VM info else deploy the VM and get the IP
        """
        if "cluster_ip" and "pe_credential" not in deployment_config:
            raise Exception("Cluster IP and PE credentials not found in the deployment config")

        cluster_ip = deployment_config["cluster_ip"]
        pe_credential = deployment_config["pe_credential"]
        ndb_vm_name = deployment_config["ndb_vm_name"]

        # now our clusters format is not same as the one we use while we are configuring clusters, so we format it
        # essentially we have to upload ndb image nand create vm in the cluster
        data = {
            "clusters": {
                cluster_ip: {
                    "pe_credential": pe_credential,
                    "images": deployment_config.get("images"),
                    "vms": [deployment_config.get("ndb_vm_config")]
                }
            }
        }
        create_pe_objects(data=data, global_data=self.data)

        # Deploy NDB VM if ndb_vm_config is present
        if deployment_config.get("ndb_vm_config"):
            try:
                self.logger.info(f"Deploying NDB VM in the cluster {deployment_config['cluster_ip']!r}...")
                self.deploy_ndb(cluster_data=data)
            except Exception as e:
                raise Exception(f"Could not deploy NDB VM in the cluster. Error: {e}")

        # Get the NDB VM IP
        self.logger.info(f"Getting the NDB VM IP from the cluster {deployment_config['cluster_ip']!r}...")
        vm_op = VM(data["clusters"][cluster_ip]["pe_session"])
        # Get the NDB VM IP
        self.ndb_ip = self.ndb_config["ndb_ip"] = (
            vm_op.get_vm_info(vm_name_list=[ndb_vm_name])[0].get("ipAddresses"))[0]

        # Wait for NDB heartbeat
        try:
            self.logger.info("Checking if NDB is alive...")
            response, status = NdbVipMonitor(session=RestAPIUtil(self.ndb_ip, user=None, pwd=None, secured=True),
                                             ndb_ip=self.ndb_ip).monitor()
            if not status:
                raise response
        except Exception as e:
            raise Exception(f"NDB is not alive to continue further. Error: {e}")

        # NDB VM was deployed
        if deployment_config.get("ndb_vm_config"):
            # Update password
            try:
                self.logger.info("Updating the NDB UI password...")
                self.update_ndb_password(self.ndb_config["ndb_credential"])
            except Exception as e:
                raise Exception(f"Could not update the NDB password. Error: {e}")

    @staticmethod
    def deploy_ndb(cluster_data: dict):
        """
        Deploy NDB VM in the cluster using Batch script
        """
        deploy_ndb_batch_scripts = BatchScript()
        log_file = f"ndb_deployment.log"

        deploy_ndb_batch_scripts.add_all([
            UploadImagePe(cluster_data, log_file=log_file),
            CreateVmPe(cluster_data, log_file=log_file),
            PowerTransitionVmPe(cluster_data, log_file=log_file)
        ])

        if deploy_ndb_batch_scripts:
            _ = deploy_ndb_batch_scripts.run()
            # if result and result.get("clusters", {}).get(cluster_ip):
            #     self.results.update(result["clusters"][cluster_ip])

    def verify(self):
        pass
