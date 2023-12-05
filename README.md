# Zero Touch Framework

A tool used to automate end-to-end deployment and configuration of Nutanix Cloud Platform without human intervention,
hence the name Zero Touch. The tool can also be extended to manage Day-1 and Day-2 operations as well.

## Usage

### Prerequisites

- Foundation Central is configured such that it can access the networks, the nodes are discoverable on.
    - For how to set up Foundation Central and provide the API key via your DHCP server, refer to
      the [Foundation Central Guide](https://portal.nutanix.com/page/documents/details?targetId=Foundation-Central-v1_5:Foundation-Central-v1_5).
- An Ubuntu VM with access to deploy and run configurations on the intended infrastructure, should be configured as
  Self-hosted GitHub Runner in the GitHub actions, to run the workflows in GitHub.
- To Deploy Prism Central:
    - The cluster on which the PC has to be deployed exists.
    - Cluster should have:
      - Appropriate name servers to download PC tar and metadata files from the file server.
      - Storage container on which PC is deployed.
      - Network on which PC is deployed.
    - Additional Static IPs for PC VMs.

This tool can be used in two (2) modes:

1. **Dev Mode**
   > This tool can also be set up locally in any popular OS and trigger the workflows/ scripts manually. Look at the
   below section
   for Dev Setup.

2. **GitOps**
   > This tool works as GitOps, i.e. using this repository to manage Infrastructure as a Code (IaaC). Each operation is
   defined as a workflow, and these workflows can be directly triggered from GitHub through various actions.
   Click [here](config/README.md) to read more about triggering GitHub pipelines.

## Dev Mode Setup

For MacOS:
  - Install [Xcode](https://apps.apple.com/us/app/xcode/id497799835)
  - Install homebrew: `/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"`.
  - Install git and openssl: `brew install git openssl`.
  - Add path to flags: `export LDFLAGS="-L$(brew --prefix openssl)/lib"` & `export CFLAGS="-I$(brew --prefix openssl)/include"`.
  - Install Python >= 3.10 (You can use [pyenv](https://realpython.com/intro-to-pyenv/) to manage multiple Python
  versions) 
    ```sh
    brew install pyenv
    pyenv install 3.10.6
    ```
  - Clone this repo and run: `make dev` from top directory.
  - Getting into virtualenv: `source venv/bin/activate`.
  - Getting out of virtualenv: `deactivate`.

For Centos:
  - Run `make centos`.
  - Install Python >= 3.10 (You can use [pyenv](https://realpython.com/intro-to-pyenv/) to manage multiple Python
  versions)
  - Clone this repo and run: `make dev` from top directory.
  - Getting into virtualenv: `source venv/bin/activate`.
  - Getting out of virtualenv: `deactivate`.

For Ubuntu:
  - Run `make ubuntu`.
  - Install Python >= 3.10 (You can use [pyenv](https://realpython.com/intro-to-pyenv/) to manage multiple Python
  versions)
  - Clone this repo and run: `make dev` from top directory.
  - Getting into virtualenv: `source venv/bin/activate`.
  - Getting out of virtualenv: `deactivate`.

### Framework Usage

```sh
> python main.py --help

usage: main.py [-h] [--workflow WORKFLOW] [--script SCRIPT] [--schema SCHEMA] -f FILE [--debug]
Description

options:
  -h, --help            show this help message and exit
  --workflow WORKFLOW   workflow to run
  --script SCRIPT       script/s to run
  --schema SCHEMA       schema for the script
  -f FILE, --file FILE  input file/s
  --debug
  ```

### How to run ZTF manually?

You can either run the pre-existing **_functional workflows_** using the `WORKFLOW` and `FILE` parameters or run
specific scripts/ operations using `SCRIPT`, `SCHEMA`, and `FILE` parameters.

- ### Running existing Workflows

  For this, the framework expects two parameters, `WORKFLOW` and `FILE` to run existing workflows.

  The supported `WORKFLOW` parameters are:
    - `imaging` - This will trigger the Imaging of nodes using Foundation Central and create Cluster/s.
    - `pod-config` - This will facilitate Pod configuration (including AZ and Cluster configurations) in parallel.
    - `calm-vm-workloads` - This will use calm-dsl to create VM workloads in Self-Service from single or multiple
      calm-dsl
      file/s.
    - `calm-edgeai-vm-workload` - This will use calm-dsl to create Edge-AI VM workload in Self-Service from single or
      multiple calm-dsl file/s.
    - `deploy-management-pc` - This will deploy Prism Central in the specified Prism Element. It also deploys NCM in the deployed
      management Prism Central, by uploading the specified OVAs & images to the PC Clusters.
    - `config-management-pc` - This will facilitate Initial PC configurations, register the PE to PC, and enable
      Foundation Central.

  Along with the functional workflow, the tool also expects an input file, to read the necessary configurations from.
  The input file/s can either be a **json/ yaml** file. You can find example configurations in
  [config/example-configs](config/example-configs) directory. Copy the required config file,
  preferably inside [config](config) directory. Pass the file/s as input and run the workflow.

  The global configurations reside in [global.json](config/global.json). The values defined here, will be inherited in
  all the functional workflows and can be overwritten in the corresponding input file/s.
    - For `imaging`, see the example input configuration [pod-deploy.yml](config/example-configs/pod-deploy.yml).
    - For `pod-config`, see the example input configuration [pod-config.yml](config/example-configs/pod-config.yml).
    - For `calm-vm-workloads`, see the example input
      configuration [create-vm-workloads.yml](config/example-configs/create-vm-workloads.yml).
    - For `calm-edgeai-vm-workload`, see the example input
      configuration [edge-ai.json](config/example-configs/edge-ai.json).
    - For `deploy-management-pc`, see the example input configuration [pod-management-deploy.yml](config/example-configs/pod-management-deploy.yml).
    - For `config-management-pc`, see the example input configuration [pod-management-config.yml](config/example-configs/pod-management-config.yml).

  #### Example: Trigger a workflow with an input file

    ```sh
    > python main.py --workflow pod-config -f config/pod-config.yml
    ```

- ### Running specific scripts/ operations

  For this, the framework expects `SCRIPT`, `SCHEMA` and `FILE` parameters to run specified scripts.
  Below is the list of supported scripts available.

    | Script                      | Operation                                     | Example config                                                                      |
    |:----------------------------|:----------------------------------------------|:------------------------------------------------------------------------------------|
    | AddAdServerPe               | Adds Active Directory in PE                   | [authentication_pe.yml](config%2Fexample-configs%2Fauthentication_pe.yml)           |
    | AddAdServerPc               | Adds Active Directory in PC                   | [add_ad_server_pc.py](framework%2Fscripts%2Fpython%2Fadd_ad_server_pc.py)           |
    | AddAdUsersOss               | Adds AdUsers in Objects                       | [directory_services_oss.yml](config%2Fexample-configs%2Fdirectory_services_oss.yml) |
    | AddDirectoryServiceOss      | Adds Active Directory in Objects              | [directory_services_oss.yml](config%2Fexample-configs%2Fdirectory_services_oss.yml) |
    | AddNameServersPc            | Adds nameservers in PC                        | [dns_ntp_pc.yml](config%2Fexample-configs%2Fdns_ntp_pc.yml)                         |
    | AddNameServersPe            | Adds nameservers in PE                        | [dns_ntp_pe.yml](config%2Fexample-configs%2Fdns_ntp_pe.yml)                         |
    | AddNtpServersPc             | Adds NTP servers in PC                        | [dns_ntp_pc.yml](config%2Fexample-configs%2Fdns_ntp_pc.yml)                         |
    | AddNtpServersPe             | Adds NTP servers in PE                        | [dns_ntp_pe.yml](config%2Fexample-configs%2Fdns_ntp_pe.yml)                         |
    | ConnectToAz                 | Connects to AZs                               | [remote_az.yml](config%2Fexample-configs%2Fremote_az.yml)                           |
    | CreateAddressGroups         | Creates Address Groups in PC                  | [address_groups_pc.yml](config%2Fexample-configs%2Faddress_groups_pc.yml)           |
    | CreateBuckets               | Creates buckets in an Objectstore             | [objectstore_buckets.yml](config%2Fexample-configs%2Fobjectstore_buckets.yml)       |
    | CreateAppFromDsl            | Creates Calm Application from calm dsl        | [create-vm-workloads.yml](config%2Fexample-configs%2Fcreate-vm-workloads.yml)       |
    | CreateNcmProject            | Creates Calm projects                         | [create-vm-workloads.yml](config%2Fexample-configs%2Fcreate-vm-workloads.yml)       |
    | CreateContainerPe           | Creates Storage container in PE               | [storage_container_pe.yml](config%2Fexample-configs%2Fstorage_container_pe.yml)     |
    | CreateKarbonClusterPc       | Creates NKE Clusters in PC                    | [nke_clusters.yml](config%2Fexample-configs%2Fnke_clusters.yml)                     |
    | CreateObjectStore           | Creates Objectstores in PC                    | [objectstore_buckets.yml](config%2Fexample-configs%2Fobjectstore_buckets.yml)       |
    | CreateCategoryPc            | Creates Categories in PC                      | [category_pc.yml](config%2Fexample-configs%2Fcategory_pc.yml)                       |
    | CreateSubnetsPc             | Creates subnets in PC                         | [subnets_pc.yml](config%2Fexample-configs%2Fsubnets_pc.yml)                         |
    | CreateProtectionPolicy      | Creates ProtectionPolicy in PC                | [protection_policy.yml](config%2Fexample-configs%2Fprotection_policy.yml)           |
    | CreateRecoveryPlan          | Creates RecoveryPlan in PC                    | [recovery_plan.yml](config%2Fexample-configs%2Frecovery_plan.yml)                   |
    | CreateRoleMappingPe         | Creates Role mapping in PE                    | [authentication_pe.yml](config%2Fexample-configs%2Fauthentication_pe.yml)           |
    | CreateRoleMappingPc         | Creates Role mapping in PC                    | [authentication_pc.yml](config%2Fexample-configs%2Fauthentication_pc.yml)           |
    | CreateNetworkSecurityPolicy | Creates Security policies in PC               | [security_policy.yml](config%2Fexample-configs%2Fsecurity_policy.yml)               |
    | CreateNcmAccount            | Creates NTNX PC account in NCM                | [ncm_account_users.yml](config%2Fexample-configs%2Fncm_account_users.yml)           |
    | CreateNcmUser               | Creates users in NCM                          | [ncm_account_users.yml](config%2Fexample-configs%2Fncm_account_users.yml)           |
    | CreateServiceGroups         | Creates Service Groups in PC                  | [service_groups.yml](config%2Fexample-configs%2Fservice_groups.yml)                 |
    | EnableDR                    | Enables DR in PC                              | [pc_creds.yml](config%2Fexample-configs%2Fpc_creds.yml)                             |
    | EnableFlow                  | Enables Flow in PC                            | [pc_creds.yml](config%2Fexample-configs%2Fpc_creds.yml)                             |
    | EnableKarbon                | Enables Karbon/ NKE in PC                     | [pc_creds.yml](config%2Fexample-configs%2Fpc_creds.yml)                             |
    | EnableObjects               | Enables Objects in PC                         | [pc_creds.yml](config%2Fexample-configs%2Fpc_creds.yml)                             |
    | InitCalmDsl                 | Initialize calm dsl                           | [create-vm-workloads.yml](config%2Fexample-configs%2Fcreate-vm-workloads.yml)       |
    | InitialClusterConfig        | Change PE password, Accept Eula, Update Pulse | [initial_cluster_config.yml](config%2Fexample-configs%2Finitial_cluster_config.yml) |
    | InitialPcConfig             | Change PC password, Accept Eula, Update Pulse | [initial_pc_config.yml](config%2Fexample-configs%2Finitial_pc_config.yml)           |
    | PcImageUpload               | Uploads images to PC clusters                 | [upload_pc_ova.yml](config%2Fexample-configs%2Fupload_pc_ova.yml)                   |
    | PcOVAUpload                 | Uploads OVAs to PC clusters                   | [upload_pc_image.yml](config%2Fexample-configs%2Fupload_pc_image.yml)               |
    | RegisterToPc                | Registers clusters to PC                      | [register_to_pc.yml](config%2Fexample-configs%2Fregister_to_pc.yml)                 |
    | ShareBucket                 | Shares a bucket with a list of users          | [objectstore_buckets.yml](config%2Fexample-configs%2Fobjectstore_buckets.yml)       |
    | UpdateDsip                  | Updates DSIP in PE                            | [update_dsip.yml](config%2Fexample-configs%2Fupdate_dsip.yml)                       |
    | EnableFC                    | Enables Foundation Central in FC              | [pc_creds.yml](config%2Fexample-configs%2Fpc_creds.yml)                             |
    | GenerateFcApiKey            | Generates Foundation Central API Key          | [generate_fc_api_key.yml](config%2Fexample-configs%2Fgenerate_fc_api_key.yml)       |
    | DeployPC                    | Deploy PC VMs in PE                           | [deploy_pc.yml](config%2Fexample-configs%2Fdeploy_pc.yml)                           |
    
  You can find example configurations in [config/example-configs](config/example-configs) directory. 
  Copy the required config file, preferably inside [config](config) directory. Pass the file/s as input and run the framework.

  Note: You can also pass the optional `schema` parameter to validate the inputs against. Check [schema.py](framework%2Fhelpers%2Fschema.py) for schema details.
  #### Example: Trigger scripts with input files

    ```sh
    > python main.py --script AddAdServerPe,CreateRoleMappingPe --schema AD_SCHEMA -f config/authentication_pe.yml
    ```
    ```sh
    > python main.py --script EnableObjects,CreateObjectStore --schema OBJECTS_SCHEMA -f config/objectstore_buckets.yml
    ```

> Note: The path to the config file, should be defined relative to the root of the project, not to the _framework_ directory
