# The Procedural Outdoors

![](https://github.com/gabriel-v/all-tracks-no-trains/raw/main/v1-bush/frames/895.png)

## How to

### NVIDIA GPU

- install debian, nvidia proprietary driver, nvidia-docker, and CUDA 11-6
- run `./r`

### CPU

- delete the `-e KUBRIC_USE_GPU=t \` line from `shell` script
- run `./r`


## Vendorized code

Copy/pasted in this repository for ease of deployment.

- kubric: [own fork](https://github.com/gabriel-v/kubric), see [original](https://github.com/google-research/kubric)
- BlenderGIS: [own fork](https://github.com/gabriel-v/BlenderGIS), see [original](https://github.com/domlysz/BlenderGIS)
