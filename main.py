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
from framework.helpers.log_utils import get_logger, ConfigureRootLogger
from framework.helpers.workflow_utils import Workflow
from framework.scripts.python import *
from framework.helpers.helper_functions import create_pe_objects, create_pc_objects, replace_config_files, \
    save_pod_logs, generate_html_from_json, create_ipam_object
from framework.helpers.schema import *
from framework.helpers.helper_functions import get_input_data, validate_input_data, save_logs, get_creds_from_vault

parser = argparse.ArgumentParser(description="Description")
parser.add_argument("--workflow", type=str, help="workflow to run", required=False)
parser.add_argument("--script", type=str, help="script/s to run", required=False)
parser.add_argument("--schema", type=str, help="schema for the script", required=False)
parser.add_argument("-f", "--file", type=str, help="input file/s", required=True)
parser.add_argument("--debug", action='store_true')
args = parser.parse_args()

# Find path to the project root
project_root = Path(__file__).parent


def main():
    # initialize the logger
    logger = get_logger(__name__)
    pre_run_actions = []
    post_run_actions = [save_logs]
    schema = {}
    scripts = []
    files = []
    workflow_type = args.workflow

    try:
        files = [os.path.join(project_root, file.strip()) for file in args.file.split(",")]

        for file in files:
            if not os.path.exists(file):
                raise FileNotFoundError("Specify the correct path of the input file or check the name!")

        if workflow_type:
            pre_run_actions = [get_input_data, get_creds_from_vault, validate_input_data]
            post_run_actions = [save_logs]
            match workflow_type:
                case "imaging":
                    schema = IMAGING_SCHEMA
                    pre_run_actions += [create_ipam_object]
                    post_run_actions = [generate_html_from_json, save_pod_logs]
                    scripts = [FoundationScript]
                case "config-cluster":
                    schema = CLUSTER_SCHEMA
                    pre_run_actions += [create_pe_objects, create_pc_objects]
                    post_run_actions.insert(0, generate_html_from_json)
                    scripts = [ClusterConfig]
                case "deploy-pc":
                    schema = DEPLOY_PC_CONFIG_SCHEMA
                    pre_run_actions += [create_pc_objects]
                    post_run_actions.insert(0, generate_html_from_json)
                    scripts = [DeployPC]
                case "config-pc":
                    schema = PC_SCHEMA
                    pre_run_actions += [create_pc_objects]
                    post_run_actions.insert(0, generate_html_from_json)
                    scripts = [PcConfig]
                case "calm-vm-workloads":
                    schema = CREATE_VM_WORKLOAD_SCHEMA
                    scripts = [InitCalmDsl, CreateAppFromDsl]
                case "calm-edgeai-vm-workload":
                    schema = CREATE_AI_WORKLOAD_SCHEMA
                    scripts = [InitCalmDsl, UpdateCalmProject, CreateBp, LaunchBp]
                # case "calm-container-workload":
                #     schema = NKE_CLUSTER_SCHEMA
                #     pre_run_actions += [create_pe_objects, create_pc_objects]
                #     scripts = [EnableNke, CreateKarbonClusterPc]
                case "pod-config":
                    schema = POD_CONFIG_SCHEMA
                    pre_run_actions += [create_ipam_object]
                    post_run_actions = [generate_html_from_json, save_pod_logs]
                    scripts = [PodConfig]
                case "deploy-management-pc":
                    schema = POD_MANAGEMENT_DEPLOY_SCHEMA
                    post_run_actions = [generate_html_from_json, save_pod_logs]
                    scripts = [DeployManagementPlane]
                case "config-management-pc":
                    schema = POD_MANAGEMENT_CONFIG_SCHEMA
                    post_run_actions = [generate_html_from_json, save_pod_logs]
                    scripts = [ConfigManagementPlane]
                # case "example-workflow-type":
                #     schema = EXAMPLE_SCHEMA  # EXAMPLE_SCHEMA is a dict defined in helpers/schema.py
                #     pre_run_actions = [new_function1, new_function2]  # either create a new actions list (or)
                #     post_run_actions += [new_function3] # modify existing actions list
                #     scripts = [ExampleScript1, ExampleScript2]  # ExampleScript1 is .py file which inherits "Script" class
                case _:
                    logger.warning("No workflow is selected")
        elif args.script:
            # Check if scripts are valid
            try:
                input_scripts = [eval(script.strip()) for script in args.script.split(",")] if args.script else []
            except Exception as e:
                logger.error("Invalid Script specified. Specify the correct Script and try again")
                raise ModuleNotFoundError(e)

            pre_run_actions = [get_input_data, validate_input_data]
            post_run_actions = [save_logs, generate_html_from_json]

            # Check if schema is valid
            if schema := args.schema:
                try:
                    schema = eval(args.schema.strip())
                except Exception as e:
                    logger.error("Invalid Schema specified. Specify the correct Schema and try again")
                    raise ModuleNotFoundError(e)
            else:
                pre_run_actions.pop()

            pre_run_actions += [create_pe_objects, create_pc_objects, create_ipam_object]

            scripts = input_scripts
        else:
            raise Exception("Select either pre-configured workflow or script to run the framework.")
    except Exception as e:
        logger.exception(e)

    if validate_input_data in pre_run_actions and not schema:
        logger.error("Schema is empty! "
                     "Schema has to be provided if validate_input_data is specified in pre_run_actions!")
        sys.exit(1)

    # create a workflow and run it
    wf_handler = Workflow(
        workflow_type=workflow_type,
        project_root=project_root,
        schema=schema,
        input_files=files
    )

    try:
        # run the pre run functions
        wf_handler.run_functions(pre_run_actions)

        # run scripts
        wf_handler.run_scripts(scripts)

    except Exception as e:
        logger.error(e)
    finally:
        # run the post run functions
        wf_handler.run_functions(post_run_actions)
    logger.info("Done!")


if __name__ == '__main__':
    # Call the main function
    debug = args.debug
    ConfigureRootLogger(debug)
    main()
