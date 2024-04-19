"""
Multi-VM Blueprint for Linux on AHV Utilizing AI datasets
"""
import os
from pathlib import Path
import yaml, json
from calm.dsl.builtins import *
from calm.dsl.providers import get_provider
from framework.helpers.general_utils import get_json_file_contents

project_root = Path(__file__).parent.parent.parent.parent.parent
json_input = get_json_file_contents(f"{project_root}/config/edge-ai.json")
ACCOUNT_NAME = json_input["account_name"]
bp_input = json_input["bp_list"]

for bp in bp_input:
    if bp["name"] == "edge-ai-test":
        #print('bp name is {}'.format(bp["name"]))
        subnet_name = bp["subnet"]
        #print('subnet is {}'.format(subnet_name))
        cluster_name = bp["cluster"]
        #print('cluster is {}'.format(cluster_name))
        image_name = bp["image"]
        #print('image is {}'.format(image_name))
        AHVProvider = get_provider("AHV_VM")
        ApiObj = AHVProvider.get_api_obj()
        acct_ref = Ref.Account(ACCOUNT_NAME)
        acct_data = acct_ref.compile()
        account_uuid = acct_data["uuid"]
        res_subnets = ApiObj.subnets(account_uuid=account_uuid)
        #print('subnet data is {}'.format(res_subnets))
        net_name_uuid_list = []
        for entity in res_subnets.get("entities", []):
            if entity['status']['cluster_reference']['name'] == cluster_name and entity['status']['name'] == subnet_name:
                x = {"name": entity['status']['name'], "uuid": entity['metadata']['uuid']}
                net_name_uuid_list.append(x)
        #print('net list is {}'.format(net_name_uuid_list))
        res_images = ApiObj.images(account_uuid=account_uuid)
        image_name_uuid_list = []
        for entity in res_images.get("entities", []):
            if entity['status']['name'] == image_name:
                x = {"name": entity['status']['name'], "uuid": entity['metadata']['uuid']}
                image_name_uuid_list.append(x)
        #print('image list is {}'.format(image_name_uuid_list))
    else:
        raise Exception("Cluster, Subnet or Image not specified")

bp_root_folder = Path(__file__).parent.parent

TSHIRT_SPEC_PATH = (f"{bp_root_folder}/tshirt-specs/tshirt_specs.yaml")
TSHIRT_SPECS = yaml.safe_load(read_file(TSHIRT_SPEC_PATH, depth=3))
COMMON_TASK_LIBRARY = f"{bp_root_folder}/common_task_library"
INSTALL_SCRIPTS_DIRECTORY = f"{COMMON_TASK_LIBRARY}/install"
DAY2_SCRIPTS_DIRECTORY = f"{COMMON_TASK_LIBRARY}/day-two"

# Secret Variables
if file_exists(f"{bp_root_folder}/.local/edge-key"):
    BP_CRED_cred_os_KEY = read_local_file(f"{bp_root_folder}/.local/edge-key")
    #print(BP_CRED_cred_os_KEY)
else:
    BP_CRED_cred_os_KEY = "nutanix"
if file_exists(f"{bp_root_folder}/.local/edge-key.pub"):
    BP_CRED_cred_os_public_KEY = read_local_file(f"{bp_root_folder}/.local/edge-key.pub")
    #print(BP_CRED_cred_os_public_KEY)
else:
    BP_CRED_cred_os_public_KEY = "nutanix"

# Credentials
BP_CRED_cred_os = basic_cred("ubuntu",BP_CRED_cred_os_KEY,name="cred_os",type="KEY",default=True)

class VM_Provision(Service):
    @action
    def NGTTools_Tasks():
        CalmTask.Exec.ssh(name="install_NGT",filename=INSTALL_SCRIPTS_DIRECTORY + "/ngt/install_ngt.sh",target=ref(VM_Provision),)

    @action
    def Configure_VM():
        CalmTask.Exec.ssh(name="ssh_key_copy",filename=INSTALL_SCRIPTS_DIRECTORY + "/ssh_key_copy.sh",target=ref(VM_Provision),)
        CalmTask.Exec.ssh(name="setup",filename=INSTALL_SCRIPTS_DIRECTORY + "/setup.sh",target=ref(VM_Provision),)
        CalmTask.Exec.ssh(name="validate driver",filename=INSTALL_SCRIPTS_DIRECTORY + "/validate_driver.sh",target=ref(VM_Provision),)

class AHVVM_Small(Substrate):
    os_type = "Linux"
    provider_type = "AHV_VM"
    provider_spec = read_ahv_spec("specs/ahv-provider-spec.yaml")
    provider_spec_editables = read_spec(os.path.join("specs", "create_spec_editables.yaml"))
    readiness_probe = readiness_probe(connection_type="SSH",disabled=False,retries="5",connection_port=22,address="@@{platform.status.resources.nic_list[0].ip_endpoint_list[0].ip}@@",delay_secs="30",credential=ref(BP_CRED_cred_os),)
    # update CPU, Memory based on environment specific configs =============================================vvvvvv
    provider_spec.spec["resources"]["num_sockets"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["small"]["num_sockets"]
    provider_spec.spec["resources"]["num_vcpus_per_socket"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["small"]["num_vcpus_per_socket"]
    provider_spec.spec["resources"]["memory_size_mib"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["small"]["memory_size_mib"]
    # update nic ===========================================================================================vvvvvv
    provider_spec.spec["resources"]["nic_list"][0]["subnet_reference"]["name"] = str(net_name_uuid_list[0]['name'])
    provider_spec.spec["resources"]["nic_list"][0]["subnet_reference"]["uuid"] = str(net_name_uuid_list[0]['uuid'])
    # update image ==========================================================================================vvvvvv
    provider_spec.spec["resources"]["disk_list"][0]["data_source_reference"]["name"] = str(image_name_uuid_list[0]['name'])
    provider_spec.spec["resources"]["disk_list"][0]["data_source_reference"]["uuid"] = str(image_name_uuid_list[0]['uuid'])

class AHVVM_Medium(AHVVM_Small):
    provider_spec = read_ahv_spec("specs/ahv-provider-spec.yaml")
    provider_spec_editables = read_spec(os.path.join("specs", "create_spec_editables.yaml"))
    readiness_probe = readiness_probe(connection_type="SSH",disabled=False,retries="5",connection_port=22,address="@@{platform.status.resources.nic_list[0].ip_endpoint_list[0].ip}@@",delay_secs="30",credential=ref(BP_CRED_cred_os),)
    # update CPU, Memory based on environment specific configs =============================================vvvvvv
    provider_spec.spec["resources"]["num_sockets"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["medium"]["num_sockets"]
    provider_spec.spec["resources"]["num_vcpus_per_socket"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["medium"]["num_vcpus_per_socket"]
    provider_spec.spec["resources"]["memory_size_mib"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["medium"]["memory_size_mib"]
    # update nic ===========================================================================================vvvvvv
    provider_spec.spec["resources"]["nic_list"][0]["subnet_reference"]["name"] = str(net_name_uuid_list[0]['name'])
    provider_spec.spec["resources"]["nic_list"][0]["subnet_reference"]["uuid"] = str(net_name_uuid_list[0]['uuid'])
    # update image ==========================================================================================vvvvvv
    provider_spec.spec["resources"]["disk_list"][0]["data_source_reference"]["name"] = str(image_name_uuid_list[0]['name'])
    provider_spec.spec["resources"]["disk_list"][0]["data_source_reference"]["uuid"] = str(image_name_uuid_list[0]['uuid'])

class AHVVM_Large(AHVVM_Small):
    provider_spec = read_ahv_spec("specs/ahv-provider-spec.yaml")
    provider_spec_editables = read_spec(os.path.join("specs", "create_spec_editables.yaml"))
    readiness_probe = readiness_probe(connection_type="SSH",disabled=False,retries="5",connection_port=22,address="@@{platform.status.resources.nic_list[0].ip_endpoint_list[0].ip}@@",delay_secs="30",credential=ref(BP_CRED_cred_os),)
    # update CPU, Memory based on environment specific configs =============================================vvvvvv
    provider_spec.spec["resources"]["num_sockets"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["large"]["num_sockets"]
    provider_spec.spec["resources"]["num_vcpus_per_socket"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["large"]["num_vcpus_per_socket"]
    provider_spec.spec["resources"]["memory_size_mib"] = TSHIRT_SPECS["linux-os"]["global"]["tshirt_sizes"]["large"]["memory_size_mib"]
    # update nic ===========================================================================================vvvvvv
    provider_spec.spec["resources"]["nic_list"][0]["subnet_reference"]["name"] = str(net_name_uuid_list[0]['name'])
    provider_spec.spec["resources"]["nic_list"][0]["subnet_reference"]["uuid"] = str(net_name_uuid_list[0]['uuid'])
    # update image ==========================================================================================vvvvvv
    provider_spec.spec["resources"]["disk_list"][0]["data_source_reference"]["name"] = str(image_name_uuid_list[0]['name'])
    provider_spec.spec["resources"]["disk_list"][0]["data_source_reference"]["uuid"] = str(image_name_uuid_list[0]['uuid'])

class AHV_Package_Sml(Package):
    services = [ref(VM_Provision)]

    @action
    def __install__():
        VM_Provision.NGTTools_Tasks(name="Install NGT")
        VM_Provision.Configure_VM(name="Configure VM")

class AHV_Package_Med(AHV_Package_Sml):
    services = [ref(VM_Provision)]

class AHV_Package_Lrg(AHV_Package_Sml):
    services = [ref(VM_Provision)]

class AHV_Deployment_Sml(Deployment):
    min_replicas = "1"
    max_replicas = "100"
    default_replicas = "@@{WORKER}@@"
    packages = [ref(AHV_Package_Sml)]
    substrate = ref(AHVVM_Small)

class AHV_Deployment_Medium(Deployment):
    min_replicas = "1"
    max_replicas = "100"
    default_replicas = "@@{WORKER}@@"
    packages = [ref(AHV_Package_Med)]
    substrate = ref(AHVVM_Medium)

class AHV_Deployment_Large(Deployment):
    min_replicas = "1"
    max_replicas = "100"
    default_replicas = "@@{WORKER}@@"
    packages = [ref(AHV_Package_Lrg)]
    substrate = ref(AHVVM_Large)

class Common(Profile):
    os_cred_public_key = CalmVariable.Simple.Secret(BP_CRED_cred_os_public_KEY,label="OS Cred Public Key",is_hidden=True,description="SSH public key for OS CRED user.")
    NFS_PATH = CalmVariable.Simple("",label="NFS Share Path",regex="^(?:[0-9]{1,3}\.){3}[0-9]{1,3}:(\/[a-zA-Z0-9_-]+)+$",validate_regex=True,is_mandatory=True,is_hidden=False,runtime=True,description="Enter the path to your IP NFS share.  For example 10.10.10.10:/sharename")
    NFS_MOUNT_POINT = CalmVariable.Simple("/mnt/data",label="NFS Mount Point",is_mandatory=False,is_hidden=True,runtime=False,description="Local NFS Mount Point")
    WORKER = CalmVariable.Simple("1",label="",is_mandatory=False,is_hidden=False,runtime=True,description="")
    NVIDIA_DRIVER_VERSION = CalmVariable.WithOptions.Predefined.string(["515.86.01"],label="Please select the NVidia driver version to be used.",default="515.86.01",is_mandatory=True,is_hidden=False,runtime=True,description="",)
    NFS_WORKING_DIRECTORY = CalmVariable.WithOptions(["nai-dl-bench-"],label="AI Training Working Directory",default="nai-dl-bench-",is_mandatory=True,is_hidden=False,runtime=True,description="",)

    @action
    def NaiDlBench_Data_Setup(name="NAI DL Bench Data Setup"):
        CalmTask.Exec.ssh(name="NaiDlBench_Data_Setup",filename=DAY2_SCRIPTS_DIRECTORY + "/nai_dl_bench_data.sh",target=ref(VM_Provision),)
        NAI_DL_BENCH_VERSION = CalmVariable.WithOptions.Predefined.string(["0.2.3"],label="Please select the version to be used.",default="0.2.3",is_mandatory=True,is_hidden=False,runtime=True,description="",)

    @action
    def AITraining(name="AI Training"):
        CalmTask.Exec.ssh(name="AI Training",filename=DAY2_SCRIPTS_DIRECTORY + "/ai_training.sh",target=ref(VM_Provision),)
        NAI_DL_BENCH_VERSION = CalmVariable.WithOptions.Predefined.string(["0.2.3"],label="Please select the version to be used.",default="0.2.3",is_mandatory=True,is_hidden=False,runtime=True,description="",)
        AI_TRAINING_OUTPUT_FOLDER = CalmVariable.Simple("training-output",label="AI Training Output Folder",is_mandatory=True,is_hidden=False,runtime=True,description="",)
        AI_TRAINING_OUTPUT_FILE = CalmVariable.Simple("resnet.pth",label="AI Training Output File",is_mandatory=True,is_hidden=False,runtime=True,description="",)
        EXTRA_PARAMS = CalmVariable.Simple("",label="AI Training Optional Parameters",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed - Enter any extra parameters needed, e.g., --quiet, etc.",)

    @action
    def AIBatchInference(name="AI Batch Inference"):
        CalmTask.Exec.ssh(name="AI Batch Inference",filename=DAY2_SCRIPTS_DIRECTORY + "/ai_inference.sh",target=ref(VM_Provision),)
        NAI_DL_BENCH_VERSION = CalmVariable.WithOptions.Predefined.string(["0.2.3"],label="Please select the version to be used.",default="0.2.3",is_mandatory=True,is_hidden=False,runtime=True,description="",)
        AI_TRAINING_OUTPUT_FOLDER = CalmVariable.Simple("",label="AI Training Output Folder",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed",)
        AI_TRAINING_OUTPUT_FOLDER_DEFAULT = CalmVariable.Simple("training-output",label="AI Training Output Folder Default Value",is_mandatory=False,is_hidden=True,runtime=False,description="Default value for the AI Training Output Folder",)
        AI_TRAINING_OUTPUT_FILE = CalmVariable.Simple("",label="AI Training Output File",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed",)
        AI_TRAINING_OUTPUT_FILE_DEFAULT = CalmVariable.Simple("resnet.pth",label="AI Training Output File Default Value",is_mandatory=False,is_hidden=True,runtime=False,description="Default value for the AI Training Output File",)
        EXTRA_PARAMS = CalmVariable.Simple("",label="AI Inference Optional Extra Parameters",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed - Enter any extra parameters needed, e.g., --quiet, etc.",)
        AI_MODEL_NAME = CalmVariable.Simple("",label="AI Training Model Name",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed - Enter the AI model name if not using the default value",)
        AI_MODEL_NAME_DEFAULT = CalmVariable.Simple("resnet50",label="AI Training Model Name Default Value",is_mandatory=False,is_hidden=True,runtime=False,description="Default value for the AI model name",)

    @action
    def AIStartInferenceService(name="AI Start Inference Service"):
        CalmTask.Exec.ssh(name="AI Start Inference Service",filename=DAY2_SCRIPTS_DIRECTORY + "/ai_inference_start.sh",target=ref(VM_Provision),)
        NAI_DL_BENCH_VERSION = CalmVariable.WithOptions.Predefined.string(["0.2.3"],label="Please select the version to be used.",default="0.2.3",is_mandatory=True,is_hidden=False,runtime=True,description="",)
        AI_TRAINING_OUTPUT_FOLDER = CalmVariable.Simple("",label="AI Training Output Folder",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed",)
        AI_TRAINING_OUTPUT_FOLDER_DEFAULT = CalmVariable.Simple("training-output",label="AI Training Output Folder Default Value",is_mandatory=False,is_hidden=True,runtime=False,description="Default value for the AI Training Output Folder",)
        AI_TRAINING_OUTPUT_FILE = CalmVariable.Simple("",label="AI Training Output File",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed",)
        AI_TRAINING_OUTPUT_FILE_DEFAULT = CalmVariable.Simple("resnet.pth",label="AI Training Output File Default Value",is_mandatory=False,is_hidden=True,runtime=False,description="Default value for the AI Training Output File",)
        EXTRA_PARAMS = CalmVariable.Simple("",label="AI Inference Optional Extra Parameters",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed - Enter any extra parameters needed, e.g., --quiet, etc.",)
        AI_MODEL_NAME = CalmVariable.Simple("",label="AI Training Model Name",is_mandatory=False,is_hidden=False,runtime=True,description="OPTIONAL - Leave blank if not needed - Enter the AI model name if not using the default value",)
        AI_MODEL_NAME_DEFAULT = CalmVariable.Simple("resnet50",label="AI Training Model Name Default Value",is_mandatory=False,is_hidden=True,runtime=False,description="Default value for the AI model name",)

    @action
    def AIStopInferenceService(name="AI Stop Inference Service"):
        CalmTask.Exec.ssh(name="AI Stop Inference Service",filename=DAY2_SCRIPTS_DIRECTORY + "/ai_inference_stop.sh",target=ref(VM_Provision),)

class AHV_Small(Common):
    deployments = [AHV_Deployment_Sml]

    @action
    def Scaleout(name="Scale Out"):
        increase_count = CalmVariable.Simple("1",label="",is_mandatory=False,is_hidden=False,runtime=True,description="",)
        CalmTask.Scaling.scale_out("@@{increase_count}@@", name="ScaleOut",target=ref(AHV_Deployment_Sml),)

    @action
    def Scalein(name="Scale In"):
        decrease_count = CalmVariable.Simple("1",label="",is_mandatory=False,is_hidden=False,runtime=True,description="",)
        CalmTask.Scaling.scale_in("@@{decrease_count}@@", name="ScaleIn",target=ref(AHV_Deployment_Sml),)

class AHV_Medium(Common):
    deployments = [AHV_Deployment_Medium]

    @action
    def Scaleout(name="Scale Out"):
        increase_count = CalmVariable.Simple("1",label="",is_mandatory=False,is_hidden=False,runtime=True,description="",)
        CalmTask.Scaling.scale_out("@@{increase_count}@@", name="ScaleOut",target=ref(AHV_Deployment_Medium),)

    @action
    def Scalein(name="Scale In"):
        decrease_count = CalmVariable.Simple("1",label="",is_mandatory=False,is_hidden=False,runtime=True,description="",)
        CalmTask.Scaling.scale_in("@@{decrease_count}@@", name="ScaleIn",target=ref(AHV_Deployment_Medium),)

class AHV_Large(Common):
    deployments = [AHV_Deployment_Large]

    @action
    def Scaleout(name="Scale Out"):
        increase_count = CalmVariable.Simple("1",label="",is_mandatory=False,is_hidden=False,runtime=True,description="",)
        CalmTask.Scaling.scale_out("@@{increase_count}@@", name="ScaleOut",target=ref(AHV_Deployment_Large),)

    @action
    def Scalein(name="Scale In"):
        decrease_count = CalmVariable.Simple("1",label="",is_mandatory=False,is_hidden=False,runtime=True,description="",)
        CalmTask.Scaling.scale_in("@@{decrease_count}@@", name="ScaleIn",target=ref(AHV_Deployment_Large),)

class Linux(Blueprint):

    services = [VM_Provision]
    packages = [AHV_Package_Sml, AHV_Package_Med, AHV_Package_Lrg]
    substrates = [AHVVM_Small, AHVVM_Medium, AHVVM_Large]
    profiles = [AHV_Small, AHV_Medium, AHV_Large ]
    credentials = [BP_CRED_cred_os]

Linux.__doc__ = read_file('mp_meta/bp-description.md')

def main():
    print(Linux.json_dumps(pprint=True))

if __name__ == "__main__":
    main()