import json
from typing import Dict
from .script import Script
from .helpers.batch_script import BatchScript
from .pc_ova_upload import PcOVAUpload
from .pc_image_upload import PcImageUpload
from .pc_ova_deploy_vm import PcOvaDeployVM
from .power_on_vm_pc import PowerOnVmPc
from .deploy_pc import DeployPC
from framework.helpers.helper_functions import create_pe_objects, create_pc_objects
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class DeployManagementPlane(Script):
    """
    Deploy Management Plane with below configs
    """

    def __init__(self, data: Dict, **kwargs):
        self.results = {}
        self.data = data
        self.pod = self.data["pod"]
        self.upload_ova_image = None
        self.deploy_management_plane_scripts = None
        super(DeployManagementPlane, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        create_pc_objects(self.pod)
        pod_name = self.pod["pod_name"]

        # Scripts to execute Management Plane configuration
        self.deploy_management_plane_scripts = BatchScript()

        # Scripts to upload ova & image which will run in parallel
        if self.pod.get("ovas") or self.pod.get("images"):
            self.upload_ova_image = BatchScript(parallel=True, results_key="Upload_OVA_Image")
            self.upload_ova_image.add_all([PcOVAUpload(self.pod, log_file=f"{pod_name}_ova_upload_ops.log"),
                                           PcImageUpload(self.pod, log_file=f"{pod_name}_image_upload_ops.log")])
            self.deploy_management_plane_scripts.add(self.upload_ova_image)

        # Script to deploy NCM in PC
        if self.pod.get("ncm"):
            self.deploy_management_plane_scripts.add(self.deploy_ncm(self.pod))

        # Script to deploy PC in PE
        if self.pod.get("clusters"):
            self.deploy_management_plane_scripts.add(self.deploy_pc(self.pod))

        # Run configuration
        result = self.deploy_management_plane_scripts.run()
        self.logger.info(json.dumps(result, indent=4))

    @staticmethod
    def deploy_ncm(data):
        """Deploy NCM in PC
        """
        ncm_batch_scripts = BatchScript(results_key="NCM")
        for ncm in data["ncm"]:
            ncm_batch_scripts.add(PcOvaDeployVM(data, cluster_name=ncm["cluster_name"],
                                                ova_name=ncm["ova_name"], new_vm_spec_list=ncm["vm_spec_list"]))
        cluster_vm_name_dict = {}
        for ova_config in data["ncm"]:
            for vm_spec in ova_config["vm_spec_list"]:
                if cluster_vm_name_dict.get(ova_config["cluster_name"]):
                    cluster_vm_name_dict[ova_config["cluster_name"]].append(vm_spec["vm_name"])
                else:
                    cluster_vm_name_dict[ova_config["cluster_name"]] = [vm_spec["vm_name"]]
        power_on_vm_batch_scripts = BatchScript(parallel=True)
        for cluster_name, vm_name_list in cluster_vm_name_dict.items():
            power_on_vm_batch_scripts.add(PowerOnVmPc(data, cluster_name, vm_name_list=vm_name_list))
        ncm_batch_scripts.add(power_on_vm_batch_scripts)
        return ncm_batch_scripts

    @staticmethod
    def deploy_pc(data):
        """Deploy PC VMs in PE
        """
        logger.info("Start PC deployments")
        deploy_pc_batch_scripts = BatchScript(results_key="DeployPcInPe")
        create_pe_objects(data)
        deploy_pc_batch_scripts.add(DeployPC(data, log_file="pc_deployment.log"))
        return deploy_pc_batch_scripts

    def verify(self):
        pass
