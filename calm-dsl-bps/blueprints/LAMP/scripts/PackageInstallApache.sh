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

sudo rpm -Uvh https://mirror.webtatic.com/yum/el7/webtatic-release.rpm
sudo yum update -y

## -*- Install httpd and php
sudo yum install -y httpd php56w php56w-mysql

## Configure php module in apache
echo "<IfModule mod_dir.c>
        DirectoryIndex index.php index.html index.cgi index.pl index.php index.xhtml index.htm
</IfModule>" | sudo tee /etc/httpd/conf.modules.d/dir.conf

echo "<?php
phpinfo();
?>" | sudo tee /var/www/html/info.php

## Restart apache service
sudo systemctl restart httpd
sudo systemctl enable httpd