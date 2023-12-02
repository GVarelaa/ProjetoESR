#!/bin/bash
core=$1
number=$2

# Source folder path
source_folder="/home/core/ProjetoESR"

# Destination folder path
destination_folder="/tmp/pycore." + core + "/"

for i in {1..number}; do
    if [ -d "$source_folder" ]; then
        # Copy the entire folder to the destination
        cp -r "$source_folder" "$destination_folder" + "/n" + i + ".conf"
        echo "Folder copied successfully."
    else
        echo "Source folder does not exist."
    fi
done

