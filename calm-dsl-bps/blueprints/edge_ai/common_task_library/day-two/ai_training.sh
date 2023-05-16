pip3 install -q -r @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/training/code/requirements.txt

if [ '@@{calm_array_index}@@' != '0' ];
then exit 0
fi

#tar -xvf $WORK_DIR/training/data/training_images.tar -C @@{NFS_MOUNT_POINT}@@/dataset
sudo mkdir @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER}@@ && sudo chmod 777 @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER}@@
echo @@{calm_array_address}@@
bash @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/training/code/run.sh -n @@{calm_int(WORKER)}@@ -h @@{calm_array_address}@@ -m @@{address}@@  -c "python3 training.py --data-folder @@{NFS_MOUNT_POINT}@@/dataset --output-folder @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER}@@ --output-model-file @@{AI_TRAINING_OUTPUT_FILE}@@ @@{EXTRA_PARAMS}@@"