import os
import pathlib
import sys
from time import sleep
from typing import Optional, Dict
from .general_utils import validate_schema, get_json_file_contents, copy_file_util, enforce_data_arg, \
    get_yml_file_contents, create_log_dir_push_logs
from .rest_utils import RestAPIUtil
from framework.scripts.python.helpers.ipam.ipam import IPAM
from .log_utils import get_logger
from json2table import convert
from framework.helpers.vault_utils import CyberArk
from .v4_api_client import ApiClientV4

logger = get_logger(__name__)

RUNS = "runs"
WORKFLOW_RUNS_DIRECTORY = "workflow-runs"
SCRIPT_RUNS_DIRECTORY = "script-runs"
FRAMEWORK_DIRECTORY = "framework"
GLOBAL_CONFIG_NAME = "global.yml"
CONFIG_DIRECTORY = "config"
DEFAULT_PRISM_USERNAME = "admin"
DEFAULT_PRISM_PASSWORD = "Nutanix/4u"

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

def get_file_path(data: Dict, file_name: str, file_path: str):
    try:
        final_path = os.path.join(data['project_root'], file_path)
        if os.path.exists(final_path):
            return final_path
        else:
            raise Exception(f'Could not find {final_path}. Certificate details or password text file cannot be empty.')
    except Exception as e:
        logger.error(
            f'Could not find {file_name} details. Certificate details or password text file cannot be empty. Error is: {e}')
        sys.exit()


@enforce_data_arg
def get_creds_from_vault(data: dict):
    if data.get('vault_to_use') not in ['cyberark', 'local']:
        raise Exception("Kindly verify if you've selected the correct vault in 'vault_to_use'")
    if data.get('vault_to_use') == 'cyberark':
        cark_data = data.get('vaults').get('cyberark').get('metadata')

        fetch_pwd = CyberArk(host=cark_data.get('host'),
                             port=cark_data.get("port", ""),
                             cert_file=get_file_path(data, 'cert_file', cark_data.get('cert_file')),
                             cert_key=get_file_path(data, 'cert_key', cark_data.get('cert_key')))

        if not data.get('vaults').get('cyberark').get('credentials'):
            raise Exception("Credential details cannot be empty. Kindly add the required details.")

        for user_type, user_info in data.get('vaults').get('cyberark').get('credentials').items():
            try:
                username, user_pwd = fetch_pwd.fetch_creds(user_info['username'],
                                                           cark_data.get('appId'), cark_data.get('safe'),
                                                           user_info.get('address'),
                                                           cark_data.get('endpoint') or "AIMWebService")
            except Exception as e:
                logger.warning(e)
                continue
            data.get('vaults').get('cyberark').get('credentials').get(user_type).update({
                'username': username,
                'password': user_pwd
            })

        # sleep for 5 seconds to avoid any issues
        sleep(5)


@enforce_data_arg
def get_input_data(data: dict) -> None:
    """
    Read data from input file and global.yml
    """
    try:
        global_config_file = os.path.join(data['project_root'], CONFIG_DIRECTORY, GLOBAL_CONFIG_NAME)
        file_ext = pathlib.Path(global_config_file).suffix
        if file_ext == ".json":
            data.update(get_json_file_contents(global_config_file))
        else:
            data.update(get_yml_file_contents(global_config_file))
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
        raise Exception("The entered input parameters is/are invalid. Please check the errors and try again!")


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
    Create a new directory and save logs for pod runs
    """
    if not data.get("pod", {}).get("pod_name"):
        raise Exception("Pod name is not specified!")

    pod_name = data["pod"]["pod_name"]

    logger.info("Pushing pod logs...")
    # create a new directory
    new_log_directory = os.path.join(data['project_root'], RUNS, "pod-runs", pod_name)
    create_log_dir_push_logs(new_log_directory, data)


@enforce_data_arg
def save_logs(data: dict):
    """
    Create a new directory and save logs for workflow and script runs
    """
    logger.info("Pushing logs...")
    # create a new directory for logs
    if data.get('workflow_type'):
        new_log_directory = os.path.join(data['project_root'], RUNS, WORKFLOW_RUNS_DIRECTORY)
    else:
        new_log_directory = os.path.join(data['project_root'], RUNS, SCRIPT_RUNS_DIRECTORY)
    create_log_dir_push_logs(new_log_directory, data)


@enforce_data_arg
def generate_html_from_json(data, store_html: Optional[bool] = True):
    if data.get("json_output"):
        build_direction = "LEFT_TO_RIGHT"
        table_attributes = {"style": "width:100%", "class": "table table-striped", "border": "1", "cellspacing": "0"}
        html = convert(data["json_output"], build_direction=build_direction, table_attributes=table_attributes)
        if store_html:
            with open("results.html", "w") as f:
                f.write(html)
        else:
            return html


@enforce_data_arg
def replace_config_files(data: dict):
    """
    Replace modified config files
    """
    example_configs_dir = os.path.join(data['project_root'], CONFIG_DIRECTORY, "example-configs")
    # replace input configs with example configs
    files = data["input_files"]

    for file in files:
        _, file_name = os.path.split(file)
        source = os.path.join(example_configs_dir, file_name)
        if os.path.exists(source):
            destination = os.path.join(data['project_root'], CONFIG_DIRECTORY, file_name)
            copy_file_util(source, destination)
            # delete_file_util(file)


@enforce_data_arg
def create_pc_objects(data: dict, global_data: Optional[Dict] = None):
    """
    This function will create necessary Pc object that can be used by the scripts
    This script does the below actions:
        1. Reads the input configs and creates a "pc_session" from pc_ip, pc_credential from the configs
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
        'pc_session': <framework.helpers.rest_utils.RestAPIUtil object at 0x1092a9570>
    }
    """

    # if pc_ip is not specified
    if "pc_ip" not in data:
        return

    global_data = global_data if global_data else {}

    # todo use read_creds after setting data as either global or data
    # vault to use can either be in data or global data
    if 'vaults' not in data:
        # check in global data
        if 'vaults' not in global_data:
            raise Exception("Kindly verify if you've selected the correct vault and if the 'vaults' "
                            "configuration exists in 'global.yml'.")
        else:
            # check vault to use is in vaults
            if global_data.get('vault_to_use') not in global_data['vaults']:
                raise Exception("Kindly verify if you've selected the correct vault in 'vault_to_use' in 'global.yml'")
            cred_details = global_data['vaults'][global_data['vault_to_use']]['credentials']
    else:
        # check vault to use is in vaults
        if data.get('vault_to_use') not in data['vaults']:
            raise Exception("Kindly verify if you've selected the correct vault in 'vault_to_use' in 'global.yml'")
        cred_details = data['vaults'][data['vault_to_use']]['credentials']

    # check if pc_username and pc_password in cred_details
    if data.get("pc_credential") or global_data.get("pc_credential"):
        pc_user = data.get("pc_credential") or global_data.get("pc_credential")

        if not cred_details.get(pc_user, {}).get('username') or not cred_details.get(pc_user, {}).get('password'):
            raise Exception(f"PC credentials not specified for the user {pc_user!r} in 'global.yml'")

        data["pc_session"] = RestAPIUtil(data["pc_ip"],
                                         user=cred_details[pc_user]['username'],
                                         pwd=cred_details[pc_user]['password'],
                                         port="9440", secured=True)
        data["v4_api_util"] = ApiClientV4(
            data["pc_ip"], "9440", cred_details[pc_user]['username'], cred_details[pc_user]['password']
            )
    else:
        logger.warning(f"Using default PC credentials for {data['pc_ip']}!")
        default_pc_password = data.get('default_pc_password')
        data["pc_session"] = RestAPIUtil(data['pc_ip'], user=DEFAULT_PRISM_USERNAME,
                                         pwd=default_pc_password or DEFAULT_PRISM_PASSWORD,
                                         port="9440", secured=True)
        data["v4_api_util"] = ApiClientV4(
            data["pc_ip"], "9440", DEFAULT_PRISM_USERNAME, default_pc_password or DEFAULT_PRISM_PASSWORD
            )


# todo this func and pc func share same logic, let's create another function to handle the common component
@enforce_data_arg
def create_ndb_objects(data: dict, global_data: Optional[Dict] = None):
    """
    This function will create necessary Ndb object that can be used by the scripts
    This script does the below actions:
        1. Reads the input configs and creates a "ndb_session" from ndb_ip, ndb_credential from the configs
         that can be used to query the PC

    Eg config: file1
    ----------------------------------
    ndb_ip: 10.1.1.1
    ndb_username: admin
    ndb_password: nutanix/4u
    ----------------------------------
    Response: self.data object -> updated

    {
        'project_root': PosixPath('path'),
        'schema': {},
        'input_files': ['file1'],
        'ndb_ip': '10.1.1.1',
        'ndb_username': 'admin',
        'ndb_password': 'nutanix/4u',
        'ndb_session': <framework.helpers.rest_utils.RestAPIUtil object at 0x1092a9570>
    }
    """

    # if ndb_ip is not specified
    if "ndb_ip" not in data:
        return

    global_data = global_data if global_data else {}

    # todo use read_creds after setting data as either global or data
    # vault to use can either be in data or global data
    if 'vaults' not in data:
        # check in global data
        if 'vaults' not in global_data:
            raise Exception("Kindly verify if you've selected the correct vault and if the 'vaults' "
                            "configuration exists in 'global.yml'.")
        else:
            # check vault to use is in vaults
            if global_data.get('vault_to_use') not in global_data['vaults']:
                raise Exception("Kindly verify if you've selected the correct vault in 'vault_to_use' in 'global.yml'")
            cred_details = global_data['vaults'][global_data['vault_to_use']]['credentials']
    else:
        # check vault to use is in vaults
        if data.get('vault_to_use') not in data['vaults']:
            raise Exception("Kindly verify if you've selected the correct vault in 'vault_to_use' in 'global.yml'")
        cred_details = data['vaults'][data['vault_to_use']]['credentials']

    # check if ndb_username and ndb_password in cred_details
    if data.get("ndb_credential") or global_data.get("ndb_credential"):
        ndb_user = data.get("ndb_credential") or global_data.get("ndb_credential")

        if not cred_details.get(ndb_user, {}).get('username') or not cred_details.get(ndb_user, {}).get('password'):
            raise Exception(f"Ndb credentials not specified for the user {ndb_user!r} in 'global.yml'")

        data["ndb_session"] = RestAPIUtil(data["ndb_ip"],
                                          user=cred_details[ndb_user]['username'],
                                          pwd=cred_details[ndb_user]['password'],
                                          secured=True)
    else:
        logger.warning(f"Using default Ndb credentials for {data['ndb_ip']}!")
        default_ndb_password = data.get('default_ndb_password')
        data["ndb_session"] = RestAPIUtil(data['ndb_ip'], user=DEFAULT_PRISM_USERNAME,
                                          pwd=default_ndb_password or DEFAULT_PRISM_PASSWORD,
                                          secured=True)


@enforce_data_arg
def create_pe_objects(data: dict, global_data: Optional[Dict] = None):
    """
    This function will create necessary Pe objects that can be used by the scripts
    This script does the below actions:
        1. Checks if data has "clusters" entity, if it exists
            i. If "cluster_ip"s are specified as keys, it creates "pe_session" from pe_credential and
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
                'pe_session': <framework.helpers.rest_utils.RestAPIUtil object at 0x1092a99f0>
            }
        }
    }
    """

    global_data = global_data if global_data else {}

    # todo use read_creds
    # vault to use can either be in data or global data
    if 'vaults' not in data:
        # check in global data
        if 'vaults' not in global_data:
            raise Exception("Kindly verify if you've selected the correct vault and if the 'vaults' "
                            "configuration exists in 'global.yml'.")
        else:
            # check vault to use is in vaults
            if global_data.get('vault_to_use') not in global_data['vaults']:
                raise Exception("Kindly verify if you've selected the correct vault in 'vault_to_use' in 'global.yml'")
            cred_details = global_data['vaults'][global_data['vault_to_use']]['credentials']
    else:
        # check vault to use is in vaults
        if data.get('vault_to_use') not in data['vaults']:
            raise Exception("Kindly verify if you've selected the correct vault in 'vault_to_use' in 'global.yml'")
        cred_details = data['vaults'][data['vault_to_use']]['credentials']

    # if clusters are specified, get their sessions
    clusters = data.get("clusters", {})
    clusters_map = {}
    for cluster_key, cluster_details in clusters.items():
        # pe_username should be either present in current object or global config
        cluster_info = {}
        # cluster_keys are IPs
        cluster_ip = cluster_key
        if cluster_details.get("name"):
            cluster_info = {"name": cluster_details["name"]}

        if "pe_credential" in cluster_details or "pe_credential" in data:
            pe_cred = cluster_details.get("pe_credential") or data.get("pe_credential")

            if not cred_details.get(pe_cred, {}).get('username') or not cred_details.get(pe_cred, {}).get('password'):
                raise Exception(f"PE credentials not specified for the user {pe_cred!r} in 'global.yml'")

            pe_session = RestAPIUtil(cluster_ip,
                                     user=cred_details[pe_cred]['username'],
                                     pwd=cred_details[pe_cred]['password'],
                                     port="9440", secured=True)
        else:
            # use default session
            logger.warning(f"Using default PE credentials for {cluster_ip}!")
            default_pe_password = data.get('default_pe_password')
            pe_session = RestAPIUtil(cluster_ip,
                                     user=DEFAULT_PRISM_USERNAME,
                                     pwd=default_pe_password or DEFAULT_PRISM_PASSWORD,
                                     port="9440", secured=True)
        # cluster_op = PeCluster(pe_session)
        # try:
        #     cluster_op.get_cluster_info()
        #     # Add cluster info by default
        #     cluster_info.update(cluster_op.cluster_info)
        # except Exception:
        #     logger.warning("Unable to connect to PE")
        #
        # if not cluster_op.cluster_info:
        #     logger.warning(f"Couldn't fetch Cluster information for the cluster {cluster_ip}")

        # Add cluster details
        clusters_map[cluster_ip] = cluster_details
        clusters_map[cluster_ip]["cluster_info"] = cluster_info
        clusters_map[cluster_ip]["pe_session"] = pe_session

    data["clusters"] = clusters_map if clusters_map else data.get("clusters", {})


@enforce_data_arg
def create_ipam_object(data: dict, global_data: Optional[Dict] = None):
    """
    This function will create necessary IPAM object that can be used by the scripts
    This script does the below actions:
        1. Reads the input configs and creates a "ipam_session" from ipam_ip, ipam_username and ipam_password
           from the configs that can be used to query the IPAM

    ----------------------------------
    Response: self.data object -> updated

    {
        'project_root': PosixPath('path'),
        'schema': {},
        'input_files': ['file1'],
        'ipam_session': <framework.scripts.python.helpers.ipam.ipam.IPAM object at 0x109700b10>
    }
    """
    global_data = global_data if global_data else {}

    # ipam to use can either be in data or global_data
    # check if ip_allocation_method is passed in data or global_data
    if 'ip_allocation_method' not in data:
        if 'ip_allocation_method' not in global_data:
            raise Exception("Kindly verify if the 'ip_allocation_method' configuration exists in 'global.yml'.")
        else:
            # check if ipam config is passed and ip_allocation_method is in ipam
            if (global_data.get('ip_allocation_method') != "static" and
               global_data.get('ip_allocation_method') not in global_data.get('ipam', {})):
                raise Exception("Kindly verify if the 'ipam' configuration exists in 'global.yml' or you've selected "
                                "the correct ipam in 'ip_allocation_method'")
            ip_allocation_method = global_data['ip_allocation_method']
            ipam_config = global_data["ipam"]
    else:
        # check if ipam config is passed and ip_allocation_method is in ipam
        if (data.get('ip_allocation_method') != "static" and data.get('ip_allocation_method')
           not in data.get('ipam', {})):
            raise Exception("Kindly verify if the 'ipam' configuration exists in 'global.yml' or you've selected the "
                            "correct ipam in 'ip_allocation_method'")
        ip_allocation_method = data['ip_allocation_method']
        ipam_config = data["ipam"]

    # check if ipam username and password in cred_details
    if ip_allocation_method != "static":
        ipam_account_credential = ipam_config[ip_allocation_method].pop("ipam_credential")
        username, password = read_creds(data=data, credential=ipam_account_credential)
        data["ipam_session"] = IPAM(vendor=ip_allocation_method,
                                    ipam_address=ipam_config[ip_allocation_method]["ipam_address"],
                                    username=username,
                                    password=password)


@enforce_data_arg
def read_creds(data: dict, credential: str) -> (str, str):
    # todo read_creds should not access data. We should have details of data in main file itself
    vault = data.get("vault_to_use")
    credential = (data.get("vaults", {}).get(vault, {}).get("credentials", {}).
                  get(credential, {"username": None, "password": None}))
    username, password = credential.get("username"), credential.get("password")
    if not username or not password:
        raise Exception(f"Credentials for the service account {credential!r} not found in the vault")

    return username, password
