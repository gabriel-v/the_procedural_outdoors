#!/bin/bash -ex

rm -rf assets_output/*

python3 export_assets_from_blend.py --blender_file cube/cube.blend  --collection jelly --output_dir assets_output/cube-jelly
