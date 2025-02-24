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
from framework.helpers.helper_functions import (create_pe_objects, create_pc_objects, save_pod_logs,
                                                generate_html_from_json, create_ipam_object)
from framework.helpers.schema import *
from framework.helpers.helper_functions import get_input_data, validate_input_data, save_logs, get_creds_from_vault

parser = argparse.ArgumentParser(description="Description")
parser.add_argument("--workflow", type=str, help="workflow to run", required=False)
parser.add_argument("--script", type=str, help="script/s to run", required=False)
parser.add_argument("--schema", type=str, help="schema for the script", required=False)
parser.add_argument("-f", "--file", type=str, help="input file/s", required=True)
parser.add_argument("--debug", action='store_true')
parser.add_argument("--uuid", type=str, help="uuid for the logs", required=False)
args = parser.parse_args()

# Find path to the project root
project_root = Path(__file__).parent

WORKFLOW_CONFIG = {
    "imaging": {
        "schema": IMAGING_SCHEMA,
        "pre_run_actions": [create_ipam_object],
        "post_run_actions": [generate_html_from_json, save_pod_logs],
        "scripts": [FoundationScript]
    },
    "config-cluster": {
        "schema": CLUSTER_SCHEMA,
        "pre_run_actions": [create_pe_objects, create_pc_objects],
        "post_run_actions": [generate_html_from_json, save_logs],
        "scripts": [ClusterConfig]
    },
    "deploy-pc": {
        "schema": DEPLOY_PC_CONFIG_SCHEMA,
        "pre_run_actions": [create_pe_objects],
        "post_run_actions": [generate_html_from_json, save_logs],
        "scripts": [DeployPC]
    },
    "config-pc": {
        "schema": PC_SCHEMA,
        "pre_run_actions": [create_pc_objects],
        "post_run_actions": [generate_html_from_json, save_logs],
        "scripts": [PcConfig]
    },
    "calm-vm-workloads": {
        "schema": CREATE_VM_WORKLOAD_SCHEMA,
        "scripts": [InitCalmDsl, CreateAppFromDsl, save_logs]
    },
    "calm-edgeai-vm-workload": {
        "schema": CREATE_AI_WORKLOAD_SCHEMA,
        "scripts": [InitCalmDsl, UpdateCalmProject, CreateBp, LaunchBp]
    },
    "pod-config": {
        "schema": POD_CONFIG_SCHEMA,
        "pre_run_actions": [create_ipam_object],
        "post_run_actions": [generate_html_from_json, save_pod_logs],
        "scripts": [PodConfig]
    },
    "deploy-management-pc": {
        "schema": POD_MANAGEMENT_DEPLOY_SCHEMA,
        "post_run_actions": [generate_html_from_json, save_pod_logs],
        "scripts": [DeployManagementPlane]
    },
    "config-management-pc": {
        "schema": POD_MANAGEMENT_CONFIG_SCHEMA,
        "post_run_actions": [generate_html_from_json, save_pod_logs],
        "scripts": [ConfigManagementPlane]
    },
    "ndb": {
        "schema": NDB_SCHEMA,
        "post_run_actions": [generate_html_from_json, save_logs],
        "scripts": [NdbConfig]
    }
}

def main():
    logger = get_logger(__name__)
    pre_run_actions = [get_input_data, get_creds_from_vault, validate_input_data]
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
            config = WORKFLOW_CONFIG.get(workflow_type)
            if config:
                schema = config.get("schema", {})
                pre_run_actions += config.get("pre_run_actions", [])
                post_run_actions = config.get("post_run_actions", post_run_actions)
                scripts = config.get("scripts", [])
            else:
                logger.warning("No workflow is selected")
        elif args.script:
            try:
                input_scripts = [eval(script.strip()) for script in args.script.split(",")] if args.script else []
            except Exception as e:
                logger.error("Invalid Script specified. Specify the correct Script and try again")
                raise ModuleNotFoundError(e)

            pre_run_actions += [create_pe_objects, create_pc_objects, create_ipam_object]
            scripts = input_scripts

            if args.schema:
                try:
                    schema = eval(args.schema.strip())
                except Exception as e:
                    logger.error("Invalid Schema specified. Specify the correct Schema and try again")
                    raise ModuleNotFoundError(e)
            else:
                pre_run_actions.remove(validate_input_data)
        else:
            raise Exception("Select either pre-configured workflow or script to run the framework.")
    except Exception as e:
        logger.exception(e)

    if validate_input_data in pre_run_actions and not schema:
        logger.error("Schema is empty! Schema has to be provided if validate_input_data is specified"
                     " in pre_run_actions!")
        sys.exit(1)

    wf_handler = Workflow(
        workflow_type=workflow_type,
        project_root=project_root,
        schema=schema,
        input_files=files
    )

    try:
        wf_handler.run_functions(pre_run_actions)
        wf_handler.run_scripts(scripts)
    except Exception as e:
        logger.error(e)
    finally:
        wf_handler.run_functions(post_run_actions)
    logger.info("Done!")

if __name__ == '__main__':
    debug = args.debug
    if args.uuid:
        ConfigureRootLogger(debug, file_name=f"{args.uuid}-zero_touch.log")
    else:
        ConfigureRootLogger(debug)
    main()
