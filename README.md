# The Procedural Outdoors

![](https://github.com/gabriel-v/all-tracks-no-trains/raw/main/v1-bush/frames/895.png)

## How to

### NVIDIA GPU

- install debian, nvidia proprietary driver, nvidia-docker, and CUDA 11-6
- run `sudo ./magic-nvidia-script.sh` once per boot, if needed
- run `./r`
- wait 24h

### CPU

- delete the `-e KUBRIC_USE_GPU=t \` line from `shell` script
- run `./r`
- wait 36h


## Vendorized code

Copy/pasted in this repository for ease of deployment.

- kubric: [own fork](https://github.com/gabriel-v/kubric), see [original](https://github.com/google-research/kubric)
- BlenderGIS: [own fork](https://github.com/gabriel-v/BlenderGIS), see [original](https://github.com/domlysz/BlenderGIS)
