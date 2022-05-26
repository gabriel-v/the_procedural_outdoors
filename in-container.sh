#!/bin/bash -ex
# time python3 extract_trees.py
if [[ "t" == "$KUBRIC_USE_GPU" ]]; then nvidia-smi; fi
time python3 worker.py
