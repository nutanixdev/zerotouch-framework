import glob
import os
import pathlib
import sys
from datetime import datetime
from helpers.general_utils import validate_schema, get_json_file_contents, create_new_directory, \
    copy_file_util, enforce_data_arg, get_yml_file_contents, delete_file_util
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.v2.cluster import Cluster as PeCluster
from helpers.log_utils import get_logger

logger = get_logger(__name__)

LOGS_DIRECTORY = "workflow_runs"
FRAMEWORK_DIRECTORY = "framework"
GLOBAL_CONFIG_NAME = "global.json"
SITES_CONFIG_DIRECTORY = "config"

"""
These are the functions that are part of pre_run_actions and post_run_actions in main.py

How to write helper functions?
    1. Add a decorator "@enforce_data_arg" to the user defined functions
    2. Define your function with argument "data". "data" will be populated with the below data at 
    the beginning of the workflow.
    eg: data["input_files"] will have the input files
        data["schema"] will have the schema specified for the input
        data["project_root"] will have the Path of project root, for file/ path manipulation
    3. You can update the "data" in the function to persist it across functions
    4. Once data is updated, it can be used by other functions
"""


# """
# This scenario will work if these functions are defined in pre_run_actions. Eg:
# pre_run_actions += [test_func1, test_func2]
#
# // Running Func 1
# // Running Func 2
# // Yay I am able to access the data I defined in previous function
# // test
# """

# @enforce_data_arg
# def test_func1(data):
#     """
#     Test data that just adds a key to data
#     """
#     print("Running Func 1")
#     data["test"] = "test"
#
#
# @enforce_data_arg
# def test_func2(data):
#     """
#     Test data that just prints a key from data
#     """
#     print("Running Func 2")
#     print("Yay I am able to access the data I defined in previous function")
#     print(data["test"])


@enforce_data_arg
def get_input_data(data: dict) -> None:
    """
    Read data from input file and global.json
    """
    try:
        global_config_file = f"{data['project_root']}/{SITES_CONFIG_DIRECTORY}/{GLOBAL_CONFIG_NAME}"
        data.update(get_json_file_contents(global_config_file))
        files = data["input_files"]

        for file in files:
            file = file.strip()
            # todo any better way to just read it in one shot? as yml is superset of json
            file_ext = pathlib.Path(file).suffix
            if file_ext == ".json":
                data.update(get_json_file_contents(file))
            else:
                data.update(get_yml_file_contents(file))
    except Exception as e:
        logger.error(e)
        sys.exit(1)


@enforce_data_arg
def validate_input_data(data: dict):
    """
    validate the input data against a schema
    """
    schema = data.get("schema")
    # initialize the validator with schema
    valid_input = validate_schema(schema, data)

    if not valid_input:
        logger.error("The entered input parameters is/are invalid. Please check the errors and try again!")
        sys.exit(1)


@enforce_data_arg
def get_aos_url_mapping(data: dict) -> None:
    """
    AOS version to url mapping
    """
    aos_version = data.get("imaging_parameters").pop("aos_version")
    aos_versions = data.get("aos_versions", {})
    if aos_version in aos_versions:
        data["aos_url"] = aos_versions[aos_version].get('url')
    else:
        raise Exception("Unsupported AOS version, verify if you have specified the supported AOS version and try again")


@enforce_data_arg
def get_hypervisor_url_mapping(data: dict) -> None:
    """
    Hypervisor version to url mapping
    """
    # get hypervisor_url
    hyp_version = str(data.get("imaging_parameters").pop("hypervisor_version"))
    hyp_type = data["imaging_parameters"]["hypervisor_type"]
    hypervisors = data.get("hypervisors", {})

    if hyp_type in hypervisors:
        if hyp_version in hypervisors[hyp_type]:
            data["hypervisor_url"] = hypervisors[hyp_type][hyp_version].get('url')
        else:
            raise Exception("Unsupported Hypervisor version, verify if you have specified the supported Hypervisor "
                            "version and try again")
    else:
        raise Exception("Unsupported Hypervisor!")


@enforce_data_arg
def save_pod_logs(data: dict):
    """
    Create a new directory and save logs
    """
    if not data.get("pod", {}).get("pod_name"):
        raise Exception("Pod name is not specified!")

    pod_name = data["pod"]["pod_name"]

    logger.info("Pushing pod logs...")
    # create a new directory
    timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H_%M_%S")

    new_log_directory = os.path.join(data['project_root'], "pod-runs", pod_name)

    # as we are using mkdir -p, this will create the branch directory, along with logs directory as well
    logs_directory = os.path.join(new_log_directory, "logs")
    create_new_directory(logs_directory)

    # push logs to the branch
    source = os.path.join(data['project_root'], FRAMEWORK_DIRECTORY)
    log_files = glob.glob(os.path.join(source, "*.log"))

    for log_file in log_files:
        _, log_file_name = os.path.split(log_file)
        destination = os.path.join(logs_directory, f"{timestamp}_{log_file_name}")
        try:
            copy_file_util(log_file, destination)
        except Exception as e:
            raise Exception(e)
        finally:
            delete_file_util(log_file)

    config_directory = os.path.join(new_log_directory, "configs")
    create_new_directory(config_directory)

    # push input configs to the branch
    files = data["input_files"]

    for file in files:
        _, file_name = os.path.split(file)
        destination = os.path.join(config_directory, f"{timestamp}_{file_name}")
        copy_file_util(file, destination)


@enforce_data_arg
def save_logs(data: dict):
    """
    Create a new directory and save logs
    """
    logger.info("Pushing logs...")
    # create a new site directory
    timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H_%M_%S")

    new_log_directory = os.path.join(data['project_root'], LOGS_DIRECTORY)
    if data.get('workflow_type'):
        new_log_directory = os.path.join(new_log_directory, data["workflow_type"])

    # as we are using mkdir -p, this will create the branch directory, along with logs directory as well
    logs_directory = os.path.join(new_log_directory, "logs")
    create_new_directory(logs_directory)

    # push logs to the branch
    source = f"{data['project_root']}/{FRAMEWORK_DIRECTORY}"
    log_files = glob.glob(os.path.join(source, "*.log"))

    for log_file in log_files:
        _, log_file_name = os.path.split(log_file)
        destination = os.path.join(logs_directory, f"{timestamp}_{log_file_name}")
        copy_file_util(log_file, destination)
        delete_file_util(log_file)

    config_directory = os.path.join(new_log_directory, "configs")
    create_new_directory(config_directory)

    # push input configs to the branch
    files = data["input_files"]

    for file in files:
        _, file_name = os.path.split(file)
        destination = os.path.join(config_directory, f"{timestamp}_{file_name}")
        copy_file_util(file, destination)


def replace_config_files(data: dict):
    """
    Replace modified config files
    """
    example_configs_dir = os.path.join(data['project_root'], SITES_CONFIG_DIRECTORY, "example-configs")
    # replace input configs with example configs
    files = data["input_files"]

    for file in files:
        _, file_name = os.path.split(file)
        source = os.path.join(example_configs_dir, file_name)
        if os.path.exists(source):
            destination = os.path.join(data['project_root'], SITES_CONFIG_DIRECTORY, file_name)
            copy_file_util(source, destination)
        else:
            delete_file_util(file)


@enforce_data_arg
def create_pc_objects(data: dict):
    """
    This function will create necessary Pc object that can be used by the scripts
    This script does the below actions:
        1. Reads the input configs and creates a "pc_session" from pc_ip, pc_username and pc_password from the configs
         that can be used to query the PC

    Eg config: file1
    ----------------------------------
    pc_ip: 10.1.1.1
    pc_username: admin
    pc_password: nutanix/4u
    ----------------------------------
    Response: self.data object -> updated

    {
        'project_root': PosixPath('path'),
        'schema': {},
        'input_files': ['file1'],
        'pc_ip': '10.1.1.1',
        'pc_username': 'admin',
        'pc_password': 'nutanix/4u',
        'pc_session': <helpers.rest_utils.RestAPIUtil object at 0x1092a9570>
    }
    """

    # If Pc details are passed, create PC session
    if data.get("pc_ip") and data.get("pc_username") and data.get("pc_password"):
        data["pc_session"] = RestAPIUtil(data["pc_ip"], user=data["pc_username"],
                                         pwd=data["pc_password"],
                                         port="9440", secured=True)


@enforce_data_arg
def create_pe_objects(data: dict):
    """
    This function will create necessary Pe objects that can be used by the scripts
    This script does the below actions:
        1. Checks if data has "clusters" entity, if it exists
            i. If "cluster_ip"s are specified as keys, it creates "pe_session" from pe_username, pe_password and
            "cluster_info" with cluster details

    Eg config: file1
    ----------------------------------
    pe_username: admin
    pe_password: nutanix/4u

    clusters:
      # configure the clusters that are already registered to a PC
      # cluster-name
      10.1.1.110:
        dsip: ''
    ----------------------------------
    Response: self.data object -> updated

    {
        'project_root': PosixPath('path'),
        'schema': {},
        'input_files': ['file1'],
        'pe_username': 'admin',
        'pe_password': 'nutanix/4u',
        'clusters': {
            '10.1.1.110': {
                'dsip': '',
                'cluster_info': {'name': 'cluster-01'},
                'pe_session': <helpers.rest_utils.RestAPIUtil object at 0x1092a99f0>
            }
        }
    }
    """

    # if clusters are specified, get their sessions
    clusters = data.get("clusters", {})

    clusters_map = {}
    for cluster_key, cluster_details in clusters.items():
        # pe_username should be either present in current object or global config
        if "pe_username" in cluster_details:
            pe_username = cluster_details["pe_username"]
        elif "pe_username" in data:
            pe_username = data["pe_username"]
        else:
            raise Exception(f"PE credentials not specified for the cluster {cluster_key}")

        # pe_password should be either present in current object or global config
        if "pe_password" in cluster_details:
            pe_password = cluster_details["pe_password"]
        elif "pe_password" in data:
            pe_password = data["pe_password"]
        else:
            raise Exception(f"PE credentials not specified for the cluster {cluster_key}")

        cluster_info = {}
        # cluster_keys are IPs
        cluster_ip = cluster_key
        if cluster_details.get("name"):
            cluster_info = {"name": cluster_details["name"]}

        # Create PE session with cluster_ip
        pe_session = RestAPIUtil(cluster_ip, user=pe_username, pwd=pe_password, port="9440", secured=True)
        cluster_op = PeCluster(pe_session)
        try:
            cluster_op.get_cluster_info()
            # Add cluster info by default
            cluster_info.update(cluster_op.cluster_info)
        except Exception as e:
            logger.warning("Unable to connect to PE")

        if not cluster_op.cluster_info:
            logger.warning(f"Couldn't fetch Cluster information for the cluster {cluster_ip}")

        # Add cluster details
        clusters_map[cluster_ip] = cluster_details
        clusters_map[cluster_ip]["cluster_info"] = cluster_info
        clusters_map[cluster_ip]["pe_session"] = pe_session

    data["clusters"] = clusters_map if clusters_map else data.get("clusters", {})
