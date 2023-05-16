# region headers
# task_name:    InstallNgt
# description:  mounts the ngt iso (assuming /dev/sr0) and installs
#               Nutanix Guest Tools.
# output vars:  none
# dependencies: none
# endregion
sudo mount /dev/sr0 /media
sudo python3 /media/installer/linux/install_ngt.py
