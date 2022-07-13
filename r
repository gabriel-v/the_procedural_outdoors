#!/bin/bash -ex
start=`date +%s`

./shell bash in-container.sh 2>&1 | tee output/logs.txt
end=`date +%s`
runtime=$((end-start))

( nohup xdg-open output > /dev/null & ) || true
( notify-send "RENDER DONE" "RENDER DONE IN $runtime" ) || true
