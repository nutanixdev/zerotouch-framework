"""
    This file is the starting point of the framework
    The process of adding new workflow/ job to the framework is as follows:
        1. Add a new workflow_type by adding a new case statement in the below match, case expression
        2. Add/ modify the pre_run_actions, post_run_actions or keep the default actions, which would run before and
        after the scripts respectively
        3. To add an action/ function to the pre_run_actions or post_run_actions, you can define the function
        preferably in "helpers/helper_functions.py" file and add to the "pre_run_actions" or "post_run_actions"
        list variables.
        4. "schema" will verify the SCHEMA of the input file. You have to define the schema in "helpers/schema.py"
        5. Finally, you'll define the Scripts that are to be executed by the workflow. You'll have to write the
        scripts in "scripts/python"
        6. Note the order in which functions/ scripts are defined in actions/ scripts is the order of execution of
        actions/ scripts
"""


import argparse
import os
import sys
from pathlib import Path
from helpers.log_utils import get_logger, ConfigureRootLogger
from helpers.workflow_utils import Workflow
from scripts.python.create_address_groups_pc import CreateAddressGroups
from scripts.python.create_bp_calm import CreateBp
from scripts.python.create_container_pe import CreateContainerPe
from scripts.python.enable_microseg_pc import EnableMicroseg
from scripts.python.foundation_script import FoundationScript
from scripts.python.create_service_groups_pc import CreateServiceGroups
from scripts.python.create_security_policy_pc import CreateNetworkSecurityPolicy
from scripts.python.launch_calm_bp import LaunchBp
from scripts.python.register_pe_to_pc import RegisterToPc
from scripts.python.add_ad_server_pe import AddAdServerPe
from scripts.python.create_rolemapping_pe import CreateRoleMapping
from scripts.python.create_pc_categories import CreateCategoryPc
from scripts.python.create_pc_subnets import CreateSubnetsPc
from scripts.python.update_dsip_pe import UpdateDsip
from helpers.helper_functions import create_pe_pc_objects
from scripts.python.update_calm_project import UpdateCalmProject
from scripts.python.init_calm_dsl import InitCalmDsl
from scripts.python.initial_cluster_config import InitialClusterConfig
from scripts.python.configure_pod import PodConfig
from helpers.schema import IMAGING_SCHEMA, CREATE_VM_WORKLOAD_SCHEMA, CREATE_AI_WORKLOAD_SCHEMA, POD_CONFIG_SCHEMA
from helpers.helper_functions import get_input_data, validate_input_data, get_aos_url_mapping, \
    get_hypervisor_url_mapping, save_logs

parser = argparse.ArgumentParser(description="Description")
parser.add_argument("--workflow", type=str, help="workflow to run", required=True)
parser.add_argument("-f", "--file", type=str, help="input file", required=True)
parser.add_argument("--debug", action='store_true')
args = parser.parse_args()

# Find path to the project root
project_root = Path(__file__).parent.parent


def main():
    workflow_type = args.workflow
    files = [f"{project_root}/{file.strip()}" for file in args.file.split(",")]

    # initialize the logger
    logger = get_logger(__name__)

    for file in files:
        if not os.path.exists(file):
            logger.error("Specify the correct path of the input file or check the name!")
            sys.exit(1)

    pre_run_actions = [get_input_data, validate_input_data]
    post_run_actions = [save_logs]
    schema = {}

    match workflow_type:
        case "imaging":
            pre_run_actions += [get_aos_url_mapping, get_hypervisor_url_mapping]
            schema = IMAGING_SCHEMA
            scripts = [FoundationScript]
        case "config-cluster":
            pre_run_actions += [create_pe_pc_objects]
            scripts = [InitialClusterConfig, RegisterToPc, AddAdServerPe, CreateRoleMapping, UpdateDsip,
                       CreateContainerPe, CreateSubnetsPc, CreateCategoryPc, EnableMicroseg,
                       CreateAddressGroups, CreateServiceGroups, CreateNetworkSecurityPolicy]
        case "calm-vm-workloads":
            schema = CREATE_VM_WORKLOAD_SCHEMA
            scripts = [InitCalmDsl, UpdateCalmProject, CreateBp, LaunchBp]
        case "calm-edgeai-vm-workload":
            schema = CREATE_AI_WORKLOAD_SCHEMA
            scripts = [InitCalmDsl, UpdateCalmProject, CreateBp, LaunchBp]
        case "pod-config":
            schema = POD_CONFIG_SCHEMA
            scripts = [PodConfig]
        # case "example-workflow-type":
        #     schema = EXAMPLE_SCHEMA  # EXAMPLE_SCHEMA is a dict defined in helpers/schema.py
        #     pre_run_actions = [new_function1, new_function2]  # either create a new actions list (or)
        #     post_run_actions += [new_function3] # modify existing actions list
        #     scripts = [ExampleScript1, ExampleScript2]  # ExampleScript1 is .py file which inherits "Script" class
        case _:
            logger.error("Select the correct workflow")
            sys.exit(1)

    if validate_input_data in pre_run_actions and not schema:
        logger.error("Schema is empty! "
                     "Schema has to be provided if validate_input_data is specified in pre_run_actions!")
        sys.exit(1)

    # create a workflow and run it
    wf_handler = Workflow(
            project_root=project_root,
            schema=schema,
            input_files=files
        )

    # run the pre run functions
    wf_handler.run_functions(pre_run_actions)

    # run scripts
    wf_handler.run_scripts(scripts)

    # run the post run functions
    wf_handler.run_functions(post_run_actions)


if __name__ == '__main__':
    # Call the main function
    debug = args.debug
    ConfigureRootLogger(debug)
    main()