# v1.3.1

## CVM Foundation version enhancement

- An additional script has been included to modify the CVM Foundation version (either upgrade or downgrade)

## Create Identity Provider (IDP) in IAM

- We now facilitate the setup of any IDPs compliant with SAML 2.0 in Prism Central

## Hypervisor hostname Configuration in Imaging

- The "hypervisor_hostname" can now be defined in [pod-deploy.yml](../../config/example-configs/pod-configs/pod-deploy.yml)
  to configure the Hypervisor hostname during Imaging

## Objects

- It is now possible to define "storage_network" and "public_network" separately when creating an Objectstore

## Cyberark

- The Cyberark integration has been enhanced to support the Cyberark AIM API

## Cluster Configuration workflow

-  HA reservation and Rebuild Capacity Reservation are now supported in the Cluster Configuration workflow