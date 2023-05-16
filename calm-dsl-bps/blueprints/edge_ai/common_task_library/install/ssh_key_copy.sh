#!/bin/bash

echo 'set -o vi' >> ~/.bashrc
echo 'alias vi=vim' >> ~/.bashrc
echo 'StrictHostKeyChecking no' > ~/.ssh/config
chmod 600 ~/.ssh/config

echo "Creating local private and public SSH Keys"
echo "@@{cred_os.secret}@@" > ~/.ssh/id_rsa
echo "@@{os_cred_public_key}@@" > ~/.ssh/id_rsa.pub
chmod 600 ~/.ssh/id_rsa