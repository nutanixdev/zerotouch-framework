# v1.3.0

## What's New

## Framework Enhancements
- Integration with CyberArk Vault for secure storage. Additional vault integrations will be included in future updates.
- Integration with Infoblox IPAM for efficient IP address management. Support for other IPAM solutions will be added in upcoming iterations.
- Centralized storage of credential and IPAM configurations in global.yml file.
- Introduction of new workflows:
  - config-cluster: Configures the cluster settings.
  - deploy-pc: Deploys the PC (Prism Central) entity.
  - config-pc: Configures the PC entities.
- ZTF now supports delete operations on both PC and PE entities.
- Improved PC deployment: If a file failed to download previously, the download process will now resume instead of starting from scratch.

## Imaging and Cluster Creation Features
- Integration with IPAM for Imaging and Cluster deployment.
- Ability to specify CVM, Host, and IPMI IPs for each node individually.
