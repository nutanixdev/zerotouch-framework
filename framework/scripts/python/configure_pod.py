import copy
import json
import time
from copy import deepcopy
from typing import Optional, Dict
from .enable_objects import EnableObjects
from .create_objectstore import CreateObjectStore
from .add_directory_service_oss import AddDirectoryServiceOss
from .add_ad_users_oss import AddAdUsersOss
from .create_bucket import CreateBucket
from .open_replication_ports_clusters import OpenRepPort
from .share_bucket import ShareBucket
from .create_calm_account import CreateNcmAccount
from .create_calm_user import CreateNcmUser
from .add_ad_server_pe import AddAdServerPe
from .connect_to_az_pc import ConnectToAz
from .create_address_groups_pc import CreateAddressGroups
from .create_calm_project import CreateNcmProject
from .create_container_pe import CreateContainerPe
from .create_nke_clusters import CreateKarbonClusterPc
from .create_pc_categories import CreateCategoryPc
from .create_pc_subnets import CreateSubnetsPc
from .create_protection_policy_pc import CreateProtectionPolicy
from .create_recovery_plan import CreateRecoveryPlan
from .create_rolemapping_pe import CreateRoleMappingPe
from .create_security_policy_pc import CreateNetworkSecurityPolicy
from .create_service_groups_pc import CreateServiceGroups
from .enable_dr_pc import EnableDR
from .enable_flow_pc import EnableFlow
from .enable_nke_pc import EnableKarbon
from .helpers.batch_script import BatchScript
from .init_calm_dsl import InitCalmDsl
from .initial_cluster_config import InitialClusterConfig
from .register_pe_to_pc import RegisterToPc
from .update_dsip_pe import UpdateDsip
from .script import Script
from .add_ntp_server_pe import AddNtpServersPe
from .add_name_server_pe import AddNameServersPe
from .add_ad_server_pc import AddAdServerPc
from .add_name_server_pc import AddNameServersPc
from .add_ntp_server_pc import AddNtpServersPc
from .create_rolemapping_pc import CreateRoleMappingPc
from .initial_pc_config import InitialPcConfig
from framework.helpers.helper_functions import create_pe_objects, create_pc_objects
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class PodConfig(Script):
    """
    Configure Pod with below configs
    """

    def __init__(self, data: Dict, **kwargs):
        self.ncm_projects = {}
        self.nke_scripts = None
        self.block_batch_scripts = {}
        self.data = data
        self.pod = self.data["pod"]
        self.blocks = self.pod.get("pod_blocks", {})
        super(PodConfig, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        start = time.time()
        self.block_batch_scripts = {}

        for block in self.blocks:
            block_name = block.get("pod_block_name").replace(" ", "")
            self.block_batch_scripts[block_name] = BatchScript(results_key=block_name)

            # Get PC session
            create_pc_objects(block, global_data=self.data)
            if block.get("edge_sites", []):
                for edge_site in block["edge_sites"]:
                    site_name = edge_site.get('site_name').replace(" ", "")

                    # First configure clusters in all the edge sites
                    if edge_site.get("clusters", []):
                        create_pe_objects(edge_site)
                        # add block pc details to cluster configurations
                        edge_site["pc_ip"] = block["pc_ip"]
                        edge_site["pc_username"] = block["pc_username"]
                        edge_site["pc_password"] = block["pc_password"]
                        edge_site["pc_session"] = block["pc_session"]
                        self.block_batch_scripts[block_name].add(
                            # ClusterConfig(data=edge_site, results_key=site_name,
                            #               log_file=f"{block_name}_{site_name}_pe_ops.log"))
                            self.configure_clusters(edge_site, results_key=site_name,
                                                    log_file=f"{block_name}_{site_name}_pe_ops.log"))

                        # If ncm subnets are specified, we'll create projects in ncm per cluster
                        for cluster in edge_site["clusters"].values():
                            if cluster.get("ncm_subnets") and cluster.get("ncm_users"):
                                self.ncm_projects[cluster["name"]] = {
                                    "subnets": cluster["ncm_subnets"],
                                    "users": cluster["ncm_users"]
                                }

                    # If nke clusters are specified add it to a container
                    if edge_site.get("nke_clusters", []):
                        edge_site["pc_session"] = block["pc_session"]
                        self.nke_scripts = self.nke_scripts or BatchScript(parallel=True)
                        self.nke_scripts.add(CreateKarbonClusterPc(edge_site, log_file=f"{block_name}_pc_ops.log"))

            # configure PC services/ entities
            self.block_batch_scripts[block_name].add(self.configure_pc(block, results_key='pc',
                                                                       log_file=f"{block_name}_pc_ops.log"))

            calm_objects_nke = BatchScript(parallel=True)

            # create project for every cluster
            if self.ncm_projects:
                calm_batch_scripts = BatchScript(results_key='ncm')
                calm_batch_scripts.add(self.configure_calm(block, log_file=f"{block_name}_calm_ops.log"))
                calm_batch_scripts.add(self.create_ncm_projects(self.ncm_projects, block_config=block,
                                                                log_file=f"{block_name}_calm_ops.log"))
                calm_objects_nke.add(calm_batch_scripts)

            # configure nke_clusters and objects in the end
            if self.nke_scripts or block.get("objects", {}).get("objectstores"):
                nke_objects_batch_scripts = BatchScript(parallel=True, results_key='pc')
                if self.nke_scripts:
                    nke_objects_batch_scripts.add(self.nke_scripts)

                # Create objects
                if block.get("objects", {}).get("objectstores"):
                    nke_objects_batch_scripts.add(self.configure_objects
                                                  (block, results_key='objects',
                                                   log_file=f"{block_name}_objects_ops.log"))
                calm_objects_nke.add(nke_objects_batch_scripts)

            self.block_batch_scripts[block_name].add(calm_objects_nke)

        for block in self.blocks:
            block_name = block.get("pod_block_name")
            result = self.block_batch_scripts[block_name].run()
            self.results.update(result)
            self.logger.info(json.dumps(result, indent=4))

        total_time = time.time() - start
        self.logger.info(f"Total time: {total_time:.2f} seconds")
        self.data["json_output"] = self.results

    @staticmethod
    def configure_clusters(data: Dict, results_key: Optional[str] = None,
                           log_file: Optional[str] = None) -> BatchScript:
        data = deepcopy(data)
        cluster_batch_scripts = BatchScript(results_key=results_key)

        # Initial cluster config in all clusters
        cluster_batch_scripts.add(InitialClusterConfig(data, log_file=log_file))

        # Add Auth -> needs InitialClusterConfig
        cluster_batch_scripts.add_all([
            AddAdServerPe(data, log_file=log_file),
            OpenRepPort(data, log_file=log_file)
        ])
        time.sleep(10)

        # Register PE to PC -> needs InitialClusterConfig
        # Create containers in PE -> needs InitialClusterConfig
        # Update DSIP -> needs InitialClusterConfig, fails if we update DSIP with Auth
        # Add Role-mappings -> needs AddAdServer
        # Add NTP servers -> InitialClusterConfig
        # Add Name servers -> InitialClusterConfig
        primary_cluster_batch_scripts = BatchScript(parallel=True)
        primary_cluster_batch_scripts.add_all([
            RegisterToPc(data, log_file=log_file),
            CreateContainerPe(data, log_file=log_file),
            UpdateDsip(data, log_file=log_file),
            CreateRoleMappingPe(data, log_file=log_file),
            AddNtpServersPe(data, log_file=log_file),
            AddNameServersPe(data, log_file=log_file)
        ])
        cluster_batch_scripts.add(primary_cluster_batch_scripts)

        # Create Subnets in PC -> needs RegisterToPc
        subnet_batch_script = BatchScript(parallel=True)
        subnet_batch_script.add(CreateSubnetsPc(data, log_file=log_file))
        cluster_batch_scripts.add(subnet_batch_script)

        return cluster_batch_scripts

    @staticmethod
    def configure_pc(data: Dict, results_key: Optional[str] = None, log_file: Optional[str] = None) -> BatchScript:
        data = deepcopy(data)
        pc_batch_scripts = BatchScript(results_key=results_key)

        # Initial PC config
        # Assumed this is already taken care in management config
        pc_batch_scripts.add(InitialPcConfig(data, log_file=log_file))

        # Add Auth -> needs PC config
        pc_batch_scripts.add(AddAdServerPc(data, log_file=log_file))
        time.sleep(10)

        # Add Role-mappings -> needs AddAdServer
        # Add NTP servers -> InitialPcConfig
        # Add Name servers -> InitialPcConfig
        pc_enable_scripts = BatchScript(parallel=True)
        pc_enable_scripts.add_all([
            EnableFlow(data, log_file=log_file),
            EnableDR(data, log_file=log_file),
            EnableKarbon(data, log_file=log_file),
            ConnectToAz(data, log_file=log_file),
            CreateRoleMappingPc(data, log_file=log_file),
            AddNtpServersPc(data, log_file=log_file),
            AddNameServersPc(data, log_file=log_file)
        ])
        pc_batch_scripts.add(pc_enable_scripts)

        # Entities without any dependencies
        # Create Categories in PC
        # Create AddressGroups
        # Create ServiceGroups
        pc_create_scripts = BatchScript(parallel=True)
        pc_create_scripts.add_all([
            CreateCategoryPc(data, log_file=log_file),
            CreateAddressGroups(data, log_file=log_file),
            CreateServiceGroups(data, log_file=log_file)
        ])
        pc_batch_scripts.add(pc_create_scripts)

        # Entities with dependencies
        # Add Security Policies -> needs CreateAddressGroups, CreateServiceGroups
        # create PP -> needs EnableDR
        pc_dependant_scripts = BatchScript(parallel=True)
        pc_dependant_scripts.add_all([
            CreateNetworkSecurityPolicy(data, log_file=log_file),
            CreateProtectionPolicy(data, log_file=log_file)
        ])
        pc_batch_scripts.add(pc_dependant_scripts)

        # create RP -> needs CreateProtectionPolicy
        pc_batch_scripts.add(CreateRecoveryPlan(data, log_file=log_file))

        return pc_batch_scripts

    @staticmethod
    def configure_calm(data: Dict, results_key: Optional[str] = None, log_file: Optional[str] = None) -> BatchScript:
        data = deepcopy(data)

        # Calm is just a PC with different IP
        data["pc_ip"] = data["ncm_vm_ip"]
        data["pc_username"] = data["ncm_username"]
        data["pc_password"] = data["ncm_password"]
        data["admin_pc_password"] = data["admin_ncm_password"]
        create_pc_objects(data)

        pc_batch_scripts = BatchScript(results_key=results_key)

        # Initial PC config
        pc_batch_scripts.add(InitialPcConfig(data, log_file=log_file))

        # Add Auth -> needs InitialClusterConfig
        pc_batch_scripts.add(AddAdServerPc(data, log_file=log_file))
        time.sleep(10)

        # Add Role-mappings -> needs AddAdServer
        # Add NTP servers -> InitialPcConfig
        # Add Name servers -> InitialPcConfig
        pc_scripts = BatchScript(parallel=True)
        pc_scripts.add_all([
            CreateRoleMappingPc(data, log_file=log_file),
            AddNtpServersPc(data, log_file=log_file),
            AddNameServersPc(data, log_file=log_file)
        ])
        pc_batch_scripts.add(pc_scripts)

        return pc_batch_scripts

    @staticmethod
    def create_ncm_projects(projects_map: Dict, block_config: Dict, results_key: Optional[str] = None,
                            log_file: Optional[str] = None) -> BatchScript:
        projects_to_create = {"projects": []}
        users_to_create = set()
        project_payload = {
            "name": "",
            "description": "",
            "subnets": {},
            "account_name": block_config.get("ncm_account", {}).get("name", "NTNX_LOCAL_AZ"),
            "users": []
        }
        for cluster_name, project_values in projects_map.items():
            payload = copy.deepcopy(project_payload)
            payload["name"] = f"project-{cluster_name}"  # project-<cluster-name>
            payload["subnets"][cluster_name] = project_values["subnets"]
            payload["users"] = project_values["users"]
            projects_to_create["projects"].append(payload)
            users_to_create = users_to_create.union(project_values["users"])

        nke_projects_batch_script = BatchScript(results_key=results_key)
        block_config["ncm_users"] = list(users_to_create)
        nke_projects_batch_script.add_all([
            InitCalmDsl(block_config, log_file=log_file),
            CreateNcmAccount(block_config, log_file=log_file),
            # Create project users first
            CreateNcmUser(block_config, log_file=log_file),
            CreateNcmProject(projects_to_create, log_file=log_file)
        ])

        return nke_projects_batch_script

    @staticmethod
    def configure_objects(data: Dict, results_key: Optional[str] = None, log_file: Optional[str] = None) -> BatchScript:
        data = deepcopy(data)

        objects_batch_scripts = BatchScript(results_key=results_key)

        objects_batch_scripts.add_all([
            EnableObjects(data, log_file=log_file),
            CreateObjectStore(data, log_file=log_file),
            AddDirectoryServiceOss(data, log_file=log_file),
            AddAdUsersOss(data, log_file=log_file),
            CreateBucket(data, log_file=log_file),
            ShareBucket(data, log_file=log_file)
        ])

        return objects_batch_scripts

    def verify(self):
        pass
