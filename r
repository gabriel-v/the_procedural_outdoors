#!/bin/bash -ex
./shell bash in-container.sh
( nohup xdg-open output > /dev/null & ) || true
