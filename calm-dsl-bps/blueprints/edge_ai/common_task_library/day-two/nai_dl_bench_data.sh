#!/bin/bash

if [ '@@{calm_array_index}@@' != '0' ];
then exit 0
fi

cd @@{NFS_MOUNT_POINT}@@

if [ ! -d @@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@ ];
then
    echo "Getting the NAI DL BENCH DATA Version @@{NAI_DL_BENCH_VERSION}@@"
    curl -O -L "https://github.com/nutanix/nai-dl-bench/archive/v@@{NAI_DL_BENCH_VERSION}@@.tar.gz" > "v@@{NAI_DL_BENCH_VERSION}@@.tar.gz"
    echo "Unzipping the NAI DL BENCH DATA Version @@{NAI_DL_BENCH_VERSION}@@"
    tar -xvf v@@{NAI_DL_BENCH_VERSION}@@.tar.gz @@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@
    mkdir -p dataset
    echo "Unzipping the training dataset to the dataset folder"
    tar -xvf @@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@/training/data/training_images.tar -C dataset
elif [ -d @@{NFS_WORKING_DIRECTORY}@@@@{NAI_DL_BENCH_VERSION}@@ ];
then
    echo "NAI DL BENCH DATA Version @@{NAI_DL_BENCH_VERSION}@@ is already present on the NFS share path @@{NFS_PATH}@@"
    exit 0
fi