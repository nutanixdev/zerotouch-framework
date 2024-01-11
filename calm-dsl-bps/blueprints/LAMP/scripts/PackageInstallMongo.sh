#!/bin/bash
set -ex

sudo yum update -y
sudo yum -y install epel-release

## Disable SELinux
sudo setenforce 0
sudo sed -i 's/permissive/disabled/' /etc/sysconfig/selinux

# Disable firewall
sudo systemctl stop firewalld || true
sudo systemctl disable firewalld || true

## Install MySQL packages
sudo yum install java -y
sudo touch /etc/yum.repos.d/mongodb-org-5.0.repo

#add below to the repo file
echo '[mongodb-org-5.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/$releasever/mongodb-org/5.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-5.0.asc' | sudo tee /etc/yum.repos.d/mongodb-5.0.repo
#####################
sudo yum install -y mongodb-org -y
sudo systemctl daemon-reload
sudo systemctl enable mongod.service
sudo systemctl start mongod