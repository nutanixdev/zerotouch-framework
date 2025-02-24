# v1.4.1

## What's New

## Framework Enhancements
- Integrated Unit Test Framework
- Introduced v4 API SDK for PC
- Added backward compatibility for v3 APIs for older PC versions by implementing a mechanism to choose the API version based on the PC build version

## Imaging Workflow Operations Update
- Support was added to specify VLAN ID in the imaging workflow

## New PE Operations
- Upload Image to PE
- Create VM in PE
- Power VM On/Off in PE

## New PC Deployment Operations
- Deploy multiple PC instances to a single Nutanix Cluster
- Select which PC to register with PE
- Enable and configure CMSP during PC deployment

## New PC Configuration Operations
- Enabled/Disabled Network Controller in PC
- Create VMs and manage power transitions
- New v4 API CRUD Operations for:
  - Categories
  - Address Groups
  - Service Groups
  - Security Policies (Flow Network Security Next-Gen)
  - VPCs  

## Initial NDB Functionality
- Deploy NDB VM in a cluster
- Configure NDB
  - Change NDB VM password
  - Enable / Disable Pulse
  - Register Clusters
  - Enable Multi-Cluster
  - Create Compute Profiles
  - Create Network Profiles
  - Enable NDB HA

## Bug fixes
- Fixed an issue where hypervisor_hostname was being ignored in the API payload
- Fixed an issue where the IPMI gateway was being passed instead of the IPMI subnet