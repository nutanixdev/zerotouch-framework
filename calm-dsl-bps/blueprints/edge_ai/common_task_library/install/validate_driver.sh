#!/bin/bash

if [ -f /proc/driver/nvidia/version ];
then
    cat /proc/driver/nvidia/version
    export PATH="$HOME/.local/bin:$PATH"
    exit 0
else
    echo "The NVDIA driver is not present on the system.  Check the output for any errors"
    exit 1
fi