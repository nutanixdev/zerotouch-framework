#!/bin/bash

if [ '@@{calm_array_index}@@' != '0' ]; then
    echo "AI Inference must be run from the first VM in the replica set"
    exit 0
fi

pip3 install -q -r @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/requirements.txt
export PATH=$PATH:/home/ubuntu/.local/bin

MODEL_NAME="@@{AI_MODEL_NAME}@@"
echo $MODEL_NAME
TRAINING_OUTPUT_FOLDER="@@{AI_TRAINING_OUTPUT_FOLDER}@@"
echo $TRAINING_OUTPUT_FOLDER
TRAINING_OUTPUT_FILE="@@{AI_TRAINING_OUTPUT_FILE}@@"
echo $TRAINING_OUTPUT_FILE

if [ -z "$MODEL_NAME" ] && [ -z "$TRAINING_OUTPUT_FOLDER" ] && [ -z "$TRAINING_OUTPUT_FILE" ];
then
    echo "bash @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME_DEFAULT}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -g 1 @@{EXTRA_PARAMS}@@"
    bash @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME_DEFAULT}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -g 1 @@{EXTRA_PARAMS}@@
elif [ -n "$MODEL_NAME" ] && [ -n "$TRAINING_OUTPUT_FOLDER" ] && [ -n "$TRAINING_OUTPUT_FILE" ];
then
    echo "@@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -m @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER}@@/@@{AI_TRAINING_OUTPUT_FILE}@@ -g 1 @@{EXTRA_PARAMS}@@"
    bash @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -m @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER}@@/@@{AI_TRAINING_OUTPUT_FILE}@@ -g 1 @@{EXTRA_PARAMS}@@
elif [ -z "$MODEL_NAME" ] && [ -z "$TRAINING_OUTPUT_FOLDER" ] && [ -n "$TRAINING_OUTPUT_FILE" ];
then
    echo "@@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME_DEFAULT}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -m @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER_DEFAULT}@@/@@{AI_TRAINING_OUTPUT_FILE}@@ -g 1 @@{EXTRA_PARAMS}@@"
    bash @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME_DEFAULT}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -m @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER_DEFAULT}@@/@@{AI_TRAINING_OUTPUT_FILE}@@ -g 1 @@{EXTRA_PARAMS}@@
elif [ -z "$MODEL_NAME" ] && [ -n "$TRAINING_OUTPUT_FOLDER" ] && [ -z "$TRAINING_OUTPUT_FILE" ];
then
    echo "@@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME_DEFAULT}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -m @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER}@@/@@{AI_TRAINING_OUTPUT_FILE_DEFAULT}@@ -g 1 @@{EXTRA_PARAMS}@@"
    bash @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME_DEFAULT}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -m @@{NFS_MOUNT_POINT}@@/@@{AI_TRAINING_OUTPUT_FOLDER}@@/@@{AI_TRAINING_OUTPUT_FILE_DEFAULT}@@ -g 1 @@{EXTRA_PARAMS}@@
elif [ -n "$MODEL_NAME" ] && [ -z "$TRAINING_OUTPUT_FOLDER" ] && [ -z "$TRAINING_OUTPUT_FILE" ];
then
    echo "@@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -g 1 @@{EXTRA_PARAMS}@@"
    bash @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/code/torchserve/run.sh -n @@{AI_MODEL_NAME}@@ -d @@{NFS_MOUNT_POINT}@@/@@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/inference/data -g 1 @@{EXTRA_PARAMS}@@
fi