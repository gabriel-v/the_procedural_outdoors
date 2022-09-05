#!/bin/bash -ex
# time python3 extract_trees.py
if [[ "t" == "$KUBRIC_USE_GPU" ]]; then nvidia-smi; fi
rm -rf /tmp/* || true
find /tmp -type f -delete || true
time python3 worker.py
