sudo sed -i "/#\$nrconf{restart} = 'i';/s/.*/\$nrconf{restart} = 'a';/" /etc/needrestart/needrestart.conf
sudo apt-get -q update
sudo apt -q install openjdk-17-jdk python3-pip -y
curl -fSsl -O https://us.download.nvidia.com/tesla/@@{NVIDIA_DRIVER_VERSION}@@/NVIDIA-Linux-x86_64-@@{NVIDIA_DRIVER_VERSION}@@.run
sudo sh NVIDIA-Linux-x86_64-@@{NVIDIA_DRIVER_VERSION}@@.run -s
sudo apt -q install openmpi-bin -y
sudo apt -q install nfs-common -y
sudo mkdir -p @@{NFS_MOUNT_POINT}@@
sudo echo "@@{NFS_PATH}@@ @@{NFS_MOUNT_POINT}@@ nfs nconnect=3 0 1" | sudo tee -a /etc/fstab
sudo mount -av
sudo mount @@{NFS_MOUNT_POINT}@@
#export WORK_DIR=ai
#sudo mkdir $WORK_DIR
#curl -O -L "https://github.com/nutanix/nai-dl-bench/archive/v0.2.0.tar.gz" > "$WORK_DIR/v0.2.0.tar.gz"
#tar -xvf $WORK_DIR/v0.2.0.tar.gz -C $WORK_DIR --strip-components=1