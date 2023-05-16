# Zero Touch Framework

A tool used to automate end to end deployment and configuration of Nutanix Cloud Platform without human intervention,
hence the name Zero Touch. The tool can also be extended to manage Day-1 and Day-2 operations as well.

## Usage

### Prerequisites
- Foundation Central configured such that it can access the networks nodes are discoverable on.
  - For how to set up Foundation Central and provide the API key via your DHCP server, refer to the [Foundation Central Guide](https://portal.nutanix.com/page/documents/details?targetId=Foundation-Central-v1_5:Foundation-Central-v1_5)
- GitHub Runner in the environment to run the workflows locally.

This tool can be used in two (2) modes:

1. **Dev Mode**
   > This tool can also be setup locally in any popular OS and trigger the workflows manually. Look at the below section
   for Dev Setup.

2. **GitOps**
   > This tool works as GitOps, i.e using this repository to manage Infrastructure as a Code (IaaC). Each operation is
   defined as a workflow, and these workflows can be directly triggered from Github through various actions.
   Click [here](config/README.md) to read more about triggering Github pipelines.


## Dev Mode Setup

- Ensure Python version >= 3.10 (You can use [pyenv](https://realpython.com/intro-to-pyenv/) to manage multiple Python
  versions)
    - If you are using pyenv, run this inside the project to use a specific version of Python.
        ```sh
        > pyenv local 3.10.8
        ```
- `make dev` to create/ use python venv (virtual environment) in $TOPDIR/venv and setup dev environment. Activate it by
  calling source `venv/bin/activate`. Use deactivate to `deactivate` the venv.

### Framework Usage

```sh
> cd framework && python main.py --help

usage: main.py [-h] --workflow WORKFLOW -f FILE [--debug]
Description

options:
  -h, --help            show this help message and exit
  --workflow WORKFLOW   workflow to run
  -f FILE, --file FILE  input file
  --debug
  ```

### Existing Workflows and Input Files

As mentioned above, the framework expects two parameters, `WORKFLOW` and `FILE`.

The framework is designed to be triggered by different **_functional workflows_**. These workflows call one or many
scripts behind the scenes to accomplish the task.
The supported workflows are:

- `imaging` - This will trigger the Imaging of nodes using Foundation Central and creates Cluster/s.
  Click [here](#prerequisites-for-imaging-workflow) to read prerequisite for imaging.
- `pod-config` - This will facilitate Pod configuration (including AZ and Cluster configurations) in parallel.
- `calm-vm-workloads` - This will use calm-dsl to create VM workloads in Self-Service from single or multiple calm-dsl
  file/s.
- `calm-edgeai-vm-workload` - This will use calm-dsl to create Edge-AI VM workload in Self-Service from single or
  multiple calm-dsl file/s.

Along with the functional workflow, the tool also expects an input file to read the necessary configurations from. The
input files can either be a **json/ yaml** file.

- The global configurations reside in [global.json](config/global.json). The values defined here, will be inherited in
  all the functional workflows and can be overwritten in the corresponding input file/s.
- For `imaging`, see the example input configuration [new-site.json](config/new-site.json).
- For `pod-config`, see the example input configuration [pod-config.yml](config/pod-config.yml).
- For `calm-vm-workloads`, see the example input
  configuration [create_vm_workloads.json](config/create-vm-workloads.json).
- For `calm-edgeai-vm-workload`, see the example input configuration [edge_ai.json](config/edge-ai.json).

### Trigger a workflow with an input file

```sh
> cd framework && python main.py --workflow pod-config -f config/pod-config.yml
```

> Note: The path to the file, should be defined relative to the root of the project, not to _framework_ directory

