import os
import pathlib
import sys
from datetime import datetime
from helpers.general_utils import validate_schema, get_json_file_contents, create_new_directory, \
    copy_file_util, enforce_data_arg, get_yml_file_contents
from helpers.general_utils import validate_ip
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.v2.cluster import Cluster as PeCluster
from scripts.python.helpers.v3.cluster import Cluster as PcCluster
from helpers.log_utils import get_logger

logger = get_logger(__name__)

SITES_DIRECTORY = "sites"
FRAMEWORK_DIRECTORY = "framework"
GLOBAL_CONFIG_NAME = "global.json"
SITES_CONFIG_DIRECTORY = "config"
LOG_NAME = "script_log.log"

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
def save_logs(data: dict):
    """
    Create a new directory and save logs
    """
    logger.info("Pushing logs...")
    # create a new site directory
    branch = data["site_name"]
    timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H:%M:%S")

    new_site_directory = f"{data['project_root']}/{SITES_DIRECTORY}/{branch}/{timestamp}"
    # as we are using mkdir -p, this will create the branch directory, along with logs directory as well
    logs_directory = f"{new_site_directory}/logs"
    create_new_directory(logs_directory)

    # push logs to the branch
    source = f"{data['project_root']}/{FRAMEWORK_DIRECTORY}/{LOG_NAME}"
    destination = f"{logs_directory}/app_logs.log"
    copy_file_util(source, destination)

    config_directory = f"{new_site_directory}/configs"
    create_new_directory(config_directory)

    # push input configs to the branch
    files = data["input_files"]

    for file in files:
        _, file_name = os.path.split(file)
        destination = f"{config_directory}/{file_name}"
        copy_file_util(file, destination)


@enforce_data_arg
def create_pe_pc_objects(data: dict):
    """
    This function will create necessary Pc and Pe objects that can be used by the scripts
    This script does the below actions:
        1. Reads the input configs and creates a "pc_session" from pc_ip, pc_username and pc_password from the configs
         that can be used to query the PC
        2. Checks if the file has "clusters" entity, if it exists
            a. If "cluster_ip"s are specified as keys, it creates "pe_session" from pe_username, pe_password and
            "cluster_info" with cluster details
            b. If "cluster_name"s are specified, we leverage PC to find the IP, create "pe_session" and create
            "cluster_info" with cluster name

    Eg config: file1
    ----------------------------------
    pc_ip: 10.1.1.1
    pc_username: admin
    pc_password: nutanix/4u
    pe_username: admin
    pe_password: nutanix/4u

    clusters:
      # configure the clusters that are already registered to a PC
      # cluster-name
      10.1.1.110:
        dsip: ''
      cluster-02: {}
      cluster-03: {}
    ----------------------------------
    Response: self.data object -> updated

    {
        'project_root': PosixPath('path'),
        'schema': {},
        'input_files': ['file1'],
        'pc_ip': '10.1.1.1',
        'pc_username': 'admin',
        'pc_password': 'nutanix/4u',
        'pe_username': 'admin',
        'pe_password': 'nutanix/4u',
        'clusters': {
            '10.1.1.110': {
                'dsip': '',
                'cluster_info': {'name': 'cluster-01', 'uuid': '0005f033-4b58-4d1a-0000-000000011115', ...},
                'pe_session': <helpers.rest_utils.RestAPIUtil object at 0x1092a99f0>
            },
            '10.1.1.111': {
                'cluster_info': {'name': 'cluster-02'},
                'pe_session': <helpers.rest_utils.RestAPIUtil object at 0x1092aa710>
            },
            '10.1.1.112': {
                'cluster_info': {'name': 'cluster-03'},
                'pe_session': <helpers.rest_utils.RestAPIUtil object at 0x1092aaf50>}
            },
            'pc_session': <helpers.rest_utils.RestAPIUtil object at 0x1092a9570>
        }
    }
    """

    # If Pc details are passed, create PC session
    if data.get("pc_ip") and data.get("pc_username") and data.get("pc_password"):
        data["pc_session"] = RestAPIUtil(data["pc_ip"], user=data["pc_username"],
                                         pwd=data["pc_password"],
                                         port="9440", secured=True)

    # if clusters are specified, get their sessions
    clusters = data.get("clusters", {})

    pc_cluster_obj = None

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
        # check if cluster keys are names or ip
        if not validate_ip("cluster_ip", cluster_key, lambda x, y: x):
            # need to fetch cluster_ip from PC if names are specified
            if data.get("pc_session"):
                if not pc_cluster_obj:
                    pc_cluster_obj = PcCluster(data["pc_session"])
                    pc_cluster_obj.get_pe_info_list()

                cluster_uuid = pc_cluster_obj.name_uuid_map.get(cluster_key)
                cluster_info = {"name": cluster_key}
                cluster_ip = pc_cluster_obj.uuid_ip_map.get(cluster_uuid)
                if not cluster_ip:
                    raise Exception(f"Cannot get Cluster IP for {cluster_key}")
            else:
                raise Exception("PC details (pc_ip, pc_username, pc_password) are to be provided when only "
                                "cluster names are specified!")
        else:
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
