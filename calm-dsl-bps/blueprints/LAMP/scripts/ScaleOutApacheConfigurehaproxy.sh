#!/bin/bash
set -ex

sudo setenforce 0
sudo sed -i 's/permissive/disabled/' /etc/sysconfig/selinux

port=80


echo "global
  log 127.0.0.1 local0
  log 127.0.0.1 local1 notice
  maxconn 4096
  quiet
  user haproxy
  group haproxy
defaults
  log     global
  mode    http
  retries 3
  timeout client 50s
  timeout connect 5s
  timeout server 50s
  option dontlognull
  option httplog
  option redispatch
  balance  roundrobin
# Set up application listeners here.
listen stats 0.0.0.0:8080
  mode http
  log global
  stats enable
  stats hide-version
  stats refresh 30s
  stats show-node
  stats uri /stats
listen admin
  bind 127.0.0.1:22002
  mode http
  stats uri /
frontend http
  maxconn 2000
  bind 0.0.0.0:80
  default_backend servers-http
backend servers-http" | sudo tee /etc/haproxy/haproxy.cfg

sudo sed -i 's/server host-/#server host-/g' /etc/haproxy/haproxy.cfg

hosts=$(echo "@@{APACHEService.address}@@" | sed 's/^,//' | sed 's/,$//' | tr "," "\n")


for host in $hosts
do
   echo "  server host-${host} ${host}:${port} weight 1 maxconn 100 check" | sudo tee -a /etc/haproxy/haproxy.cfg
done

sudo systemctl daemon-reload
sudo systemctl enable haproxy
sudo systemctl restart haproxy
