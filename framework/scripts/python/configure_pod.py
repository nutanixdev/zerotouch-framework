import copy
import json
import time
from copy import deepcopy
from typing import Optional
from helpers.helper_functions import create_pe_objects, create_pc_objects
from scripts.python.add_ad_server_pe import AddAdServerPe
from scripts.python.connect_to_az_pc import ConnectToAz
from scripts.python.create_address_groups_pc import CreateAddressGroups
from scripts.python.create_calm_project import CreateNcmProject
from scripts.python.create_container_pe import CreateContainerPe
from scripts.python.create_nke_clusters import CreateKarbonClusterPc
from scripts.python.create_pc_categories import CreateCategoryPc
from scripts.python.create_pc_subnets import CreateSubnetsPc
from scripts.python.create_protection_policy_pc import CreateProtectionPolicy
from scripts.python.create_recovery_plan import CreateRecoveryPlan
from scripts.python.create_rolemapping_pe import CreateRoleMapping
from scripts.python.create_security_policy_pc import CreateNetworkSecurityPolicy
from scripts.python.create_service_groups_pc import CreateServiceGroups
from scripts.python.enable_dr_pc import EnableDR
from scripts.python.enable_flow_pc import EnableFlow
from scripts.python.enable_nke_pc import EnableKarbon
from scripts.python.helpers.batch_script import BatchScript
from scripts.python.init_calm_dsl import InitCalmDsl
from scripts.python.initial_cluster_config import InitialClusterConfig
from scripts.python.register_pe_to_pc import RegisterToPc
from scripts.python.script import Script
from helpers.log_utils import get_logger
from scripts.python.update_dsip_pe import UpdateDsip

logger = get_logger(__name__)


class PodConfig(Script):
    """
    Configure Pod with below configs
    """

    def __init__(self, data: dict, **kwargs):
        self.results = {}
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
            create_pc_objects(block)
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
                        self.nke_scripts = self.nke_scripts or BatchScript(parallel=True, results_key='pc')
                        self.nke_scripts.add(CreateKarbonClusterPc(edge_site, log_file=f"{block_name}_pc_ops.log"))

            # configure PC services/ entities
            self.block_batch_scripts[block_name].add(self.configure_pc(block, results_key='pc',
                                                                       log_file=f"{block_name}_pc_ops.log"))

            # configure nke_clusters in the end due to dependencies
            if self.nke_scripts:
                self.block_batch_scripts[block_name].add(self.nke_scripts)

            # create project for every cluster
            if self.ncm_projects:
                self.block_batch_scripts[block_name].add(
                    self.create_ncm_projects(self.ncm_projects, block_config=block, results_key='ncm',
                                             log_file=f"{block_name}_calm_ops.log"))

        for block in self.blocks:
            block_name = block.get("pod_block_name")
            result = self.block_batch_scripts[block_name].run()
            self.logger.info(json.dumps(result, indent=4))

        total_time = time.time() - start
        self.logger.info(f"Total time: {total_time:.2f} seconds")

    @staticmethod
    def configure_clusters(data: dict, results_key: Optional[str] = None, log_file: Optional[str] = None) -> BatchScript:
        data = deepcopy(data)
        cluster_batch_scripts = BatchScript(results_key=results_key)

        # Initial cluster config in all clusters
        cluster_batch_scripts.add(InitialClusterConfig(data, log_file=log_file))

        # Add Auth -> needs InitialClusterConfig
        cluster_batch_scripts.add(AddAdServerPe(data, log_file=log_file))

        # Register PE to PC -> needs InitialClusterConfig
        # Create containers in PE -> needs InitialClusterConfig
        # Update DSIP -> needs InitialClusterConfig, fails if we update DSIP with Auth
        # Add Role-mappings -> needs AddAdServer
        primary_cluster_batch_scripts = BatchScript(parallel=True)
        primary_cluster_batch_scripts.add_all([
            RegisterToPc(data, log_file=log_file),
            CreateContainerPe(data, log_file=log_file),
            UpdateDsip(data, log_file=log_file),
            CreateRoleMapping(data, log_file=log_file),
        ])
        cluster_batch_scripts.add(primary_cluster_batch_scripts)

        # Create Subnets in PC -> needs RegisterToPc
        subnet_batch_script = BatchScript(parallel=True)
        subnet_batch_script.add(CreateSubnetsPc(data, log_file=log_file))
        cluster_batch_scripts.add(subnet_batch_script)

        return cluster_batch_scripts

    @staticmethod
    def configure_pc(data: dict, results_key: Optional[str] = None, log_file: Optional[str] = None) -> BatchScript:
        data = deepcopy(data)
        pc_batch_scripts = BatchScript(results_key=results_key)

        # Services without any dependencies
        # Enable Flow in PC
        # Enable Leap -> Needs UpdateDsip in all Clusters
        # EnableKarbon -> Needs UpdateDsip in all Clusters
        # Create AZs in PC
        pc_enable_scripts = BatchScript(parallel=True)
        pc_enable_scripts.add_all([
            EnableFlow(data, log_file=log_file),
            EnableDR(data, log_file=log_file),
            EnableKarbon(data, log_file=log_file),
            ConnectToAz(data, log_file=log_file)
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
    def create_ncm_projects(projects_map: dict, block_config: dict, results_key: Optional[str] = None,
                            log_file: Optional[str] = None) -> BatchScript:
        projects_to_create = {"projects": []}
        project_payload = {
            "name": "",
            "description": "",
            "subnets": {},
            "account_name": block_config.get("ncm_account"),
            "users": []
        }
        for cluster_name, project_values in projects_map.items():
            payload = copy.deepcopy(project_payload)
            payload["name"] = f"project-{cluster_name}"  # project-<cluster-name>
            payload["subnets"][cluster_name] = project_values["subnets"]
            payload["users"] = project_values["users"]
            projects_to_create["projects"].append(payload)

        nke_projects_batch_script = BatchScript(results_key=results_key)
        nke_projects_batch_script.add_all([
            InitCalmDsl(block_config, log_file=log_file),
            CreateNcmProject(projects_to_create, log_file=log_file)
        ])

        return nke_projects_batch_script

    def verify(self):
        pass
