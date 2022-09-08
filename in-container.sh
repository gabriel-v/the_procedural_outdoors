#!/bin/bash -ex
# time python3 extract_trees.py

if [[ "t" == "$KUBRIC_USE_GPU" ]]; then nvidia-smi; fi

rm -rf /tmp/* || true
find /tmp -type f -delete || true

for x in $(echo sky_alt cloud_seed  sky_illum sky_sum_int \
         sky_sun_elev sky_sun_rot sky_air_density \
         sky_dust_density sky_ozone cloud_thickness \
         cloud_spread | xargs -n1 -P1 echo | sort -R); do
    if [ -d demo_output/$x ]; then
        echo "FOLDER EXISTS, SKIPPING: demo_output/$x"
        continue
    fi
    echo " ################################## "
    echo " #                                # "
    echo " #                                # "
    echo " #   PARAM RUNNING:  $x           # "
    echo " #                                # "
    echo " #                                # "
    echo " ################################## "
    echo "$x" > output/params
    time python3 worker.py $x
    mkdir -p demo_output/$x
    mv output/* demo_output/$x
    mv demo_output/$x/trains.blend demo_output/trains.blend
done
