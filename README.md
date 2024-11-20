[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)  [![GitHub: Actions](https://img.shields.io/badge/GitHub-Actions-blue.svg?logo=github)](ACTIONS)

# Zero Touch Framework

ZTF is a tool used to automate end-to-end deployment and configuration of Nutanix Cloud Platform without human
intervention,
hence the name Zero Touch. The tool can also be extended to manage Day-1 and Day-2 operations as well.
> Note: ZTF has been primarily built to automate Nutanix Validated Designs at scale. All the existing workflows and
> scripts have been tested against: AOS: 6.5.x, 6.7.x, 6.8.x PC 2022.6.x, 2023.4.x, 2024.1.x Calm 3.5.2 and 3.6.0

## Prerequisites

- For Imaging and Cluster creation:
    - Foundation Central is enabled and configured such that it can access the networks, the nodes are discoverable on.
      For how to enable, set up Foundation Central and provide the API key to your DHCP server, refer to
      the [Foundation Central Guide](https://portal.nutanix.com/page/documents/details?targetId=Foundation-Central-v1_5:Foundation-Central-v1_5).
    - Set up a local web server for downloading AOS tar and AHV iso files.
    - If AOS and AHV files are downloaded over https from Web Server, it needs to have a valid cert issued by a trusted
      certificate authority (CA). Certificates from a custom CA are not accepted. If
      we need to skip this validation for https, we need to upgrade the Foundation version on the CVMs to 5.6.0.1 and
      above.
- For dark-site deployments:
    - Web Server needs to be setup to download the images, if there are any operations related to image upload and
      download (PC deploy, Image Upload, Ova upload etc.)
- For running ZTF using GitHub Actions (GitHub workflows):
    - A GitHub Self-hosted Runner Ubuntu VM with access to deploy and run configurations on the intended infrastructure
      configured in the GitHub actions to run the workflows.
- For running ZTF locally on a VM
    - Click [here](dev-setup-README.md) to read about how to set up environment to run ZTF locally

## Running ZTF using GitHub Actions

This tool works as GitOps, i.e. using this repository to manage Infrastructure as Code (IaC). The workflows and scripts
can
be directly triggered from GitHub through various actions.
Click [here](config/README.md) to read more about triggering GitHub Actions.

## Running ZTF locally on a VM

The first file that needs to be configured is the [global.yml](config/global.yml). Here, we will define the Vault and
IPAM configuration.

Once global.yml is defined, you can either run the pre-existing **_functional workflows_** using the `WORKFLOW`
and `FILE` parameters or run
specific **_scripts_** using `SCRIPT`, `SCHEMA`, and `FILE` parameters.

### Running existing Workflows

Below are the pre-defined workflows and how to run these workflows.

Also, there are several workflows below that support **_Pod_** deployment and configuration.
Here, ["Enterprise Edge Pod Conceptual Design"](https://portal.nutanix.com/page/documents/solutions/details?targetId=NVD-2180-Enterprise-Edge-AI:NVD-2180-Enterprise-Edge-AI)
is used to deploy and manage infrastructure at scale. In this design, a **_Pod_** can manage several
**_blocks (pod_blocks)_** and each **_block (pod_block)_** can manage multiple **_edge_sites_** and each **_edge_site_**
can manage multiple **_clusters_** at the edge.

- `imaging`
    - This is a **_Pod_** workflow.
    - This workflow is used to **Image the nodes** using Foundation Central and **create Clusters**. An example config
      template is provided
      in [config/example-configs/pod-configs/pod-deploy.yml](config/example-configs/pod-configs/pod-deploy.yml). Copy
      this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
      ```sh
      python main.py --workflow imaging -f config/pod-deploy.yml
      ```
    - Note: If you are not using the **Pod** conceptual design and just want to image nodes and create clusters, just
      enter dummy values for "pod_name" and "pod_block_name" in
      the [example-config](config/example-configs/pod-configs/pod-deploy.yml).
- `pod-config`
    - This is a **_Pod_** workflow.
    - This workflow is used to **configure** the **Pod**. An example config template is provided
      in [config/example-configs/pod-configs/pod-config.yml](config/example-configs/pod-configs/pod-config.yml). Copy
      this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
      ```sh
      python main.py --workflow pod-config -f config/pod-config.yml
      ```
    - Using the **Pod** conceptual design, you can configure the block PC (pc_ip) and clusters at the edge (edge_sites).
    - This workflow can also be used when you want to configure both PC and the clusters at the same time.
- `deploy-management-pc`
    - This is a **_Pod_** workflow.
    - This will deploy **Prism Centrals** in the specified **Clusters** and also deploys **NCM** in the deployed Prism
      Central. An example config template is provided
      in [config/example-configs/pod-configs/pod-management-deploy.yml](config/example-configs/pod-configs/pod-management-deploy.yml).
      Copy this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
      ```sh
      python main.py --workflow deploy-management-pc -f config/pod-management-deploy.yml
      ```
- `config-management-pc`
    - This is a **_Pod_** workflow.
    - This will perform Initial configurations on the deployed **Prism Centrals** and **NCMs** in the **Pod**. We can
      also
      specify the **clusters** that need to be registered to this deployed Prism Central. An example config template is
      provided
      in [config/example-configs/pod-configs/pod-management-config.yml](config/example-configs/pod-configs/pod-management-config.yml).
      Copy this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
        ```sh
      python main.py --workflow config-management-pc -f config/pod-management-config.yml
      ```
- `deploy-pc`
    - This will deploy **Prism Centrals** in the specified **Clusters**. An example config template is provided
      in [config/example-configs/workflow-configs/pc-deploy.yml](config/example-configs/workflow-configs/pc-deploy.yml).
      Copy this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
        ```sh
      python main.py --workflow deploy-pc -f config/pc-deploy.yml
      ```
- `config-pc`
    - This will configure the deployed **Prism Centrals**. An example config template is provided
      in [config/example-configs/workflow-configs/pc-config.yml](config/example-configs/workflow-configs/pc-config.yml).
      Copy this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
        ```sh
      python main.py --workflow config-pc -f config/pc-config.yml
      ```
- `config-cluster`
    - This will configure the newly deployed **Clusters**. An example config template is provided
      in [config/example-configs/workflow-configs/cluster-config.yml](config/example-configs/workflow-configs/cluster-config.yml).
      Copy this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
        ```sh
      python main.py --workflow config-cluster -f config/cluster-config.yml
      ```
- `calm-vm-workloads`
    - This will use calm-dsl to create VM workloads on Clusters using NCM Self-Service from single or multiple calm-dsl
      files. An example config template is provided
      in [config/example-configs/workflow-configs/create-vm-workloads.yml](config/example-configs/workflow-configs/create-vm-workloads.yml).
      Copy this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
        ```sh
      python main.py --workflow calm-vm-workloads -f config/create-vm-workloads.yml
      ```
- `calm-edgeai-vm-workload`
    - This will use calm-dsl to create Edge-AI VM workload on Clusters using NCM Self-Service from single or multiple
      calm-dsl files. An example config template is provided
      in [config/example-configs/workflow-configs/edge-ai.json](config/example-configs/workflow-configs/edge-ai.json).
      Copy this to the **config** directory, modify the configuration and then run this workflow using the command below
      inside **virtualenv**.
        ```sh
      python main.py --workflow calm-edgeai-vm-workload -f config/edge-ai.json
      ```  

To summarize, the input files can either be **json** or **yaml** files. You can find example configurations in
[config/example-configs](config/example-configs) directory. Copy the required config file, inside [config](config)
directory. Pass the `-f` and `--workflow` as inputs and run the workflow.

### Running individual scripts or operations

If we don't want to use pre-defined workflows, we can always run the needed operations with the below scripts. For this,
the framework expects `SCRIPT`, `SCHEMA` and `FILE` parameters to run the specified scripts, where `SCHEMA` is
optional. `SCHEMA` if specified verifies the correctness of input configuration.
Below is the list of supported scripts available.

| Script                       | Operation                                      | Example config                                                                                 |
|:-----------------------------|:-----------------------------------------------|:-----------------------------------------------------------------------------------------------|
| AddAdServerPe                | Adds Active Directory in PE                    | [authentication_pe.yml](config/example-configs/script-configs/authentication_pe.yml)           |
| AddAdServerPc                | Adds Active Directory in PC                    | [add_ad_server_pc.py](config/example-configs/script-configs/authentication_pc.yml)             |
| AddAdUsersOss                | Adds AdUsers in Objects                        | [directory_services_oss.yml](config/example-configs/script-configs/directory_services_oss.yml) |
| AddDirectoryServiceOss       | Adds Active Directory in Objects               | [directory_services_oss.yml](config/example-configs/script-configs/directory_services_oss.yml) |
| AddNameServersPc             | Adds nameservers in PC                         | [dns_ntp_pc.yml](config/example-configs/script-configs/dns_ntp_pc.yml)                         |
| AddNameServersPe             | Adds nameservers in PE                         | [dns_ntp_pe.yml](config/example-configs/script-configs/dns_ntp_pe.yml)                         |
| AddNtpServersPc              | Adds NTP servers in PC                         | [dns_ntp_pc.yml](config/example-configs/script-configs/dns_ntp_pc.yml)                         |
| AddNtpServersPe              | Adds NTP servers in PE                         | [dns_ntp_pe.yml](config/example-configs/script-configs/dns_ntp_pe.yml)                         |
| ConnectToAz                  | Connects to AZs                                | [remote_az.yml](config/example-configs/script-configs/remote_az.yml)                           |
| CreateAddressGroups          | Creates Address Groups in PC                   | [address_groups_pc.yml](config/example-configs/script-configs/address_groups_pc.yml)           |
| CreateBuckets                | Creates buckets in an Objectstore              | [objectstore_buckets.yml](config/example-configs/script-configs/objectstore_buckets.yml)       |
| CreateAppFromDsl             | Creates Calm Application from calm dsl         | [create-vm-workloads.yml](config/example-configs/workflow-configs/create-vm-workloads.yml)     |
| CreateNcmProject             | Creates Calm projects                          | [create-vm-workloads.yml](config/example-configs/workflow-configs/create-vm-workloads.yml)     |
| CreateContainerPe            | Creates Storage container in PE                | [storage_container_pe.yml](config/example-configs/script-configs/storage_container_pe.yml)     |
| CreateKarbonClusterPc        | Creates NKE Clusters in PC                     | [nke_clusters.yml](config/example-configs/script-configs/nke_clusters.yml)                     |
| CreateObjectStore            | Creates Objectstores in PC                     | [objectstore_buckets.yml](config/example-configs/script-configs/objectstore_buckets.yml)       |
| CreateCategoryPc             | Creates Categories in PC                       | [category_pc.yml](config/example-configs/script-configs/category_pc.yml)                       |
| CreateSubnetsPc              | Creates subnets in PC                          | [subnets_pc.yml](config/example-configs/script-configs/subnets_pc.yml)                         |
| CreateProtectionPolicy       | Creates ProtectionPolicy in PC                 | [protection_policy.yml](config/example-configs/script-configs/protection_policy.yml)           |
| CreateRecoveryPlan           | Creates RecoveryPlan in PC                     | [recovery_plan.yml](config/example-configs/script-configs/recovery_plan.yml)                   |
| CreateRoleMappingPe          | Creates Role mapping in PE                     | [authentication_pe.yml](config/example-configs/script-configs/authentication_pe.yml)           |
| CreateRoleMappingPc          | Creates Role mapping in PC                     | [authentication_pc.yml](config/example-configs/script-configs/authentication_pc.yml)           |
| CreateNetworkSecurityPolicy  | Creates Security policies in PC                | [security_policy.yml](config/example-configs/script-configs/security_policy.yml)               |
| CreateNcmAccount             | Creates NTNX PC account in NCM                 | [ncm_account_users.yml](config/example-configs/script-configs/ncm_account_users.yml)           |
| CreateNcmUser                | Creates users in NCM                           | [ncm_account_users.yml](config/example-configs/script-configs/ncm_account_users.yml)           |
| CreateServiceGroups          | Creates Service Groups in PC                   | [service_groups.yml](config/example-configs/script-configs/service_groups.yml)                 |
| EnableDR                     | Enables DR in PC                               | [pc_creds.yml](config/example-configs/script-configs/pc_creds.yml)                             |
| EnableMicrosegmentation      | Enables Flow in PC                             | [pc_creds.yml](config/example-configs/script-configs/pc_creds.yml)                             |
| EnableNke                    | Enables Karbon/ NKE in PC                      | [pc_creds.yml](config/example-configs/script-configs/pc_creds.yml)                             |
| EnableObjects                | Enables Objects in PC                          | [pc_creds.yml](config/example-configs/script-configs/pc_creds.yml)                             |
| InitCalmDsl                  | Initialize calm dsl                            | [create-vm-workloads.yml](config/example-configs/workflow-configs/create-vm-workloads.yml)     |
| ChangeDefaultAdminPasswordPe | Change PE admin password                       | [initial_cluster_config.yml](config/example-configs/script-configs/initial_cluster_config.yml) |
| AcceptEulaPe                 | Accept Eula PE                                 | [initial_cluster_config.yml](config/example-configs/script-configs/initial_cluster_config.yml) |
| UpdatePulsePe                | Update Pulse PE                                | [initial_cluster_config.yml](config/example-configs/script-configs/initial_cluster_config.yml) |
| ChangeDefaultAdminPasswordPc | Change PC password                             | [initial_pc_config.yml](config/example-configs/script-configs/initial_pc_config.yml)           |
| AcceptEulaPc                 | Accept Eula PC                                 | [initial_pc_config.yml](config/example-configs/script-configs/initial_pc_config.yml)           |
| UpdatePulsePc                | Update Pulse PC                                | [initial_pc_config.yml](config/example-configs/script-configs/initial_pc_config.yml)           |
| PcImageUpload                | Uploads images to PC clusters                  | [pc_image.yml](config/example-configs/script-configs/pc_image.yml)                             |
| PcOVAUpload                  | Uploads OVAs to PC clusters                    | [pc_ova.yml](config/example-configs/script-configs/pc_ova.yml)                                 |
| RegisterToPc                 | Registers clusters to PC                       | [register_to_pc.yml](config/example-configs/script-configs/register_to_pc.yml)                 |
| ShareBucket                  | Shares a bucket with a list of users           | [objectstore_buckets.yml](config/example-configs/script-configs/objectstore_buckets.yml)       |
| UpdateDsip                   | Updates DSIP in PE                             | [update_dsip.yml](config/example-configs/script-configs/update_dsip.yml)                       |
| EnableFC                     | Enables Foundation Central in FC               | [pc_creds.yml](config/example-configs/script-configs/pc_creds.yml)                             |
| GenerateFcApiKey             | Generates Foundation Central API Key           | [generate_fc_api_key.yml](config/example-configs/script-configs/generate_fc_api_key.yml)       |
| DeleteSubnetsPc              | Delete Subnets in PC                           | [subnets_pc.yml](config/example-configs/script-configs/delete_subnets_pc.yml)                  |
| DeleteSubnetsPe              | Delete Subnets in PE                           | [subnets_pe.yml](config/example-configs/script-configs/delete_subnets_pc.yml)                  |
| DeleteAdServerPc             | Delete Active Directory in PC                  | [authentication_pc.yml](config/example-configs/script-configs/authentication_pc.yml)           |
| DeleteAdServerPe             | Delete Active Directory in PE                  | [authentication_pe.yml](config/example-configs/script-configs/authentication_pe.yml)           |
| DeleteAddressGroups          | Delete Address Groups in PC                    | [address_groups_pc.yml](config/example-configs/script-configs/address_groups_pc.yml)           |
| DeleteNameServersPc          | Delete Name Servers in PC                      | [dns_ntp_pc.yml](config/example-configs/script-configs/authentication_pc.yml)                  |
| DeleteNameServersPe          | Delete Name Servers in PE                      | [dns_ntp_pe.yml](config/example-configs/script-configs/authentication_pc.yml)                  |
| DeleteNtpServersPc           | Delete NTP Servers in PC                       | [dns_ntp_pc.yml](config/example-configs/script-configs/authentication_pc.yml)                  |
| DeleteNtpServersPe           | Delete NTP Servers in PE                       | [dns_ntp_pe.yml](config/example-configs/script-configs/authentication_pc.yml)                  |
| DeleteCategoryPc             | Delete Categories in PC                        | [category_pc.yml](config/example-configs/script-configs/authentication_pc.yml)                 |
| DeleteProtectionPolicy       | Delete Protection Policies in PC               | [protection_policy.yml](config/example-configs/script-configs/protection_policy.yml)           |
| DeleteRecoveryPlan           | Delete Recovery Plans in PC                    | [recovery_plan.yml](config/example-configs/script-configs/recovery_plan.yml)                   |
| DeleteRoleMappingPc          | Delete Role Mappings in PC                     | [authentication_pc.yml](config/example-configs/script-configs/authentication_pc.yml)           |
| DeleteRoleMappingPe          | Delete Role Mappings in PE                     | [authentication_pc.yml](config/example-configs/script-configs/authentication_pc.yml)           |
| DeleteNetworkSecurityPolicy  | Delete Security Policies in PC                 | [security_policy.yml](config/example-configs/script-configs/security_policy.yml)               |
| DeleteServiceGroups          | Delete Service Groups in PC                    | [service_groups.yml](config/example-configs/script-configs/service_groups.yml)                 |
| DeleteVmPc                   | Delete VMs in PC                               | [delete_vms_pc.yml](config/example-configs/script-configs/authentication_pc.yml)               |
| DeleteVmPe                   | Delete VMs in PE                               | [delete_vms_pe.yml](config/example-configs/script-configs/authentication_pc.yml)               |
| DisconnectAz                 | Disconnects Availability Zones in PC           | [remote_az.yml](config/example-configs/script-configs/remote_az.yml)                           |
| PcImageDelete                | Delete Images in PC                            | [pc_image.yml](config/example-configs/script-configs/pc_image.yml)                             |
| PcOVADelete                  | Delete OVAs in PC                              | [pc_ova.yml](config/example-configs/script-configs/pc_ova.yml)                                 |
| CreateIdp                    | Create SAML2 compliant Identity Provider in PC | [saml_idp.yml](config/example-configs/script-configs/saml_idp.yml)                             |
| UpdateCvmFoundation          | Update CVM Foundation Version                  | [update_cvm_foundation.yml](config/example-configs/script-configs/update_cvm_foundation.yml)   |
| HaReservation                | Enable/Disable HA Reservation in PE            | [ha.yml](config/example-configs/script-configs/ha.yml)                                         |
| RebuildCapacityReservation   | Enable/Disable Rebuild Capacity Reservation in PE | [rebuild_capcity_reservation.yml](config/example-configs/script-configs/rebuild_capcity_reservation.yml)                            |

To summarize, the input files can either be **json** or **yaml** files. You can find example configurations in
[config/example-configs](config/example-configs) directory. Copy the required config file, inside [config](config)
directory. Pass the `-f` and `--script` as inputs and run the workflow.

Note: You can also pass the optional `schema` parameter to validate the inputs against.
Check [schema.py](framework/helpers/schema.py) for schema details.

#### Example: Trigger scripts with input files

```sh
  > python main.py --script AddAdServerPe,CreateRoleMappingPe --schema AD_CREATE_SCHEMA -f config/authentication_pe.yml
```

```sh
  > python main.py --script EnableObjects,CreateObjectStore --schema OBJECTS_CREATE_SCHEMA -f config/objectstore_buckets.yml
```

> Note: The path to the config file, should be defined relative to the root of the project, not to the _framework_
> directory
