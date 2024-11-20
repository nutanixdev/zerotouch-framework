import copy
import json
import time
from copy import deepcopy
from typing import Optional, Dict
from framework.scripts.python.ncm.configure_calm import CalmConfig
from framework.scripts.python.pe.configure_cluster import ClusterConfig
from framework.scripts.python.objects.configure_objects import OssConfig
from framework.scripts.python.pc.configure_pc import PcConfig
from framework.scripts.python.ncm.account.create_calm_account import CreateNcmAccount
from framework.scripts.python.ncm.project.create_calm_user import CreateNcmUser
from framework.scripts.python.ncm.project.create_calm_project import CreateNcmProject
from framework.scripts.python.nke.create_nke_clusters import CreateKarbonClusterPc
from .helpers.batch_script import BatchScript
from framework.scripts.python.ncm.init_calm_dsl import InitCalmDsl
from .script import Script
from framework.helpers.log_utils import get_logger
from framework.helpers.helper_functions import create_pc_objects

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
                        # add block pc details to cluster configurations
                        edge_site["pc_ip"] = block["pc_ip"]
                        edge_site["pc_credential"] = block["pc_credential"]
                        edge_site["pc_session"] = block["pc_session"]
                        self.block_batch_scripts[block_name].add(
                            ClusterConfig(data=deepcopy(edge_site), global_data=self.data, results_key=site_name,
                                          log_file=f"{block_name}_{site_name}_pe_ops.log"))

                        # If ncm subnets are specified, we'll create projects in ncm per cluster
                        for cluster in edge_site["clusters"].values():
                            if cluster.get("ncm_subnets") and cluster.get("ncm_users"):
                                self.ncm_projects[cluster["name"]] = {
                                    "subnets": cluster["ncm_subnets"],
                                    "users": cluster["ncm_users"]
                                }

                    # If nke clusters are specified add it to a variable
                    if edge_site.get("nke_clusters", []):
                        edge_site["pc_session"] = block["pc_session"]
                        self.nke_scripts = self.nke_scripts or BatchScript(parallel=True)
                        self.nke_scripts.add(CreateKarbonClusterPc(edge_site, global_data=self.data,
                                                                   log_file=f"{block_name}_pc_ops.log"))

            # configure PC services/ entities
            self.block_batch_scripts[block_name].add(PcConfig(data=deepcopy(block), global_data=self.data,
                                                              results_key='pc', log_file=f"{block_name}_pc_ops.log"))

            calm_objects_nke = BatchScript(parallel=True)

            # create project for every cluster
            if self.ncm_projects:
                calm_batch_scripts = BatchScript(results_key='ncm')
                calm_batch_scripts.add(CalmConfig(data=deepcopy(block), global_data=self.data,
                                                  log_file=f"{block_name}_calm_ops.log"))
                calm_batch_scripts.add(self.create_ncm_projects(self.ncm_projects, global_data=self.data,
                                                                block_config=block,
                                                                log_file=f"{block_name}_calm_ops.log"))
                calm_objects_nke.add(calm_batch_scripts)

            # configure nke_clusters and objects in parallel in the end
            if self.nke_scripts or block.get("objects", {}).get("objectstores"):
                nke_objects_batch_scripts = BatchScript(parallel=True, results_key='pc')
                if self.nke_scripts:
                    nke_objects_batch_scripts.add(self.nke_scripts)

                # Create objects
                if block.get("objects", {}).get("objectstores"):
                    nke_objects_batch_scripts.add(OssConfig(data=deepcopy(block), global_data=self.data,
                                                            results_key='objects',
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
    def create_ncm_projects(projects_map: Dict, block_config: Dict, global_data: Dict,
                            results_key: Optional[str] = None, log_file: Optional[str] = None) -> BatchScript:
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

        if not block_config.get("vaults"):
            block_config["vaults"] = global_data.get("vaults")
        if not block_config.get("vault_to_use"):
            block_config["vault_to_use"] = global_data.get("vault_to_use")

        nke_projects_batch_script = BatchScript(results_key=results_key)
        block_config["ncm_users"] = list(users_to_create)
        nke_projects_batch_script.add_all([
            InitCalmDsl(block_config, global_data=global_data, log_file=log_file),
            CreateNcmAccount(block_config, global_data=global_data, log_file=log_file),
            # Create project users first
            CreateNcmUser(block_config, log_file=log_file),
            CreateNcmProject(projects_to_create, log_file=log_file)
        ])

        return nke_projects_batch_script

    def verify(self):
        pass
