#!/bin/bash
set -ex

sudo yum install -y "http://repo.mysql.com/mysql-community-release-el7-5.noarch.rpm"

## Disable SELinux
sudo setenforce 0
sudo sed -i 's/permissive/disabled/' /etc/sysconfig/selinux

# Disable firewall
sudo systemctl stop firewalld || true
sudo systemctl disable firewalld || true

sudo yum update -y
sudo yum install -y mysql-community-server.x86_64

sudo /bin/systemctl start mysqld
sudo /bin/systemctl enable mysqld


## Enable and start MySQL Services
sudo systemctl enable mysqld
sudo systemctl start mysqld

## Fix to obtain temp password and set it to blank
password=$(sudo grep -oP 'temporary password(.*): \K(\S+)' /var/log/mysqld.log)
sudo mysqladmin --user=root --password="$password" password aaBB**cc1122
sudo mysql --user=root --password=aaBB**cc1122 -e "UNINSTALL COMPONENT 'file://component_validate_password'"
sudo mysqladmin --user=root --password="aaBB**cc1122" password ""

## -*- Mysql secure installation
mysql -u root<<-EOF
ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY '@@{MYSQL_PASSWORD}@@';
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
DELETE FROM mysql.user WHERE User='';
DELETE FROM mysql.db WHERE Db='test' OR Db='test\_%';
FLUSH PRIVILEGES;
EOF

