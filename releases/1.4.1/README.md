# v1.4.1

## What's New

## Framework Enhancements
- Integrated Unit Test Framework
- Introduced v4 API SDK for PC
- Added backward compatibility for v3 APIs for older PC versions by implementing a mechanism to choose the API version based on the PC build version

## Initial NDB Functionality
- Deploy & Configure NDB Management
  - Deploy NDB VMs
  - Change NDB VM password
  - Register NDB Clusters
  - Enable NDB Multi-Cluster
  - Create Compute Profiles
  - Create Network Profiles
  - Enable NDB HA
  - Enable / Disable Pulse

## New  Operations Functionalities

### Imaging Workflow Update
- Added support to specify VLAN ID in the imaging workflow

### PE Operations
- Upload Image to PE
- Create VM in PE
- Power VM On/Off in PE

### PC Deployment Operations
- Deploy multiple PC instances to a single Nutanix Cluster
- Select which PC to register with PE
- Enable and configure CMSP during PC deployment

### PC Configuration Operations
- Enabled/Disabled Network Controller in PC
- Create VMs and manage power transitions
- New v4 API CRUD Operations for:
  - Categories
  - Address Groups
  - Service Groups
  - Security Policies (Flow Network Security Next-Gen)
  - VPCs

## Bug fixes
- Fixed an issue where hypervisor_hostname was being ignored in the API payload
- Fixed an issue where the IPMI gateway was being passed instead of the IPMI subnet