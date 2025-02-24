# v1.4

## What's New

### Framework Enhancements
- Introduced v4 API SDK for PC.
- Added backward compatibility for v3 APIs for older PC versions by implementing a mechanism to choose the API version based on the PC build version.
- Integrated unit test framework for the ZTF.

### PC operations
- Enabled/disabled the network controller in PC.
- Added functionality to create, update, and delete categories in PC using v4 APIs.
- Added functionality to create, update, and delete address groups in PC using v4 APIs.
- Added functionality to create, update, and delete service groups in PC using v4 APIs.
- Added functionality to create, update, and delete security policies (Flow Next Gen).
- Added functionality to create, update, and delete VPCs.
- Added functionality to create, VMs and manage power transitions.

### NDB
- Added functionality to deploy NDB VM in a cluster.
- Added functionalities to configure NDB
  - Change NDB VM password.
  - Enabling/ Disabling pulse.
  - Register Clusters.
  - Enable multi-cluster.
  - Create compute-profiles.
  - Create network-profiles.
  - Enable HA.

### PE operations
- Upload Image to PE.
- Create VM in PE.
- Power on/off VM in PE.

### PC Deployment
- Ability to deploy multiple PC instances in a single cluster.
- Added functionality to select which PC to register with PE.
- Added functionality to enable and configure CMSP during PC deployment.