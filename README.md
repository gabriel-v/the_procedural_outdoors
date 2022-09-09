# The Procedural Outdoors

![](https://github.com/gabriel-v/all-tracks-no-trains/raw/main/v1-bush/frames/895.png)

## How to

- `sudo apt-get install -y imagemagick ffmpeg`
- install docker from https://get.docker.com
- continue depending on hardware:

### NVIDIA GPU

- install nvidia proprietary driver >= v510, nvidia-docker, and CUDA >= v11-6
- run `sudo ./magic-nvidia-script.sh` once per boot, if needed
- run `./r`
- watch things appear in the `output` and `demo_output` folders
- wait 24h

### CPU

- delete the `-e KUBRIC_USE_GPU=t \` line from `shell` script
- run `./r`
- watch things appear in the `output` and `demo_output` folders
- wait 36h


## Vendorized code

Copy/pasted in this repository for ease of deployment.

- kubric: [own fork](https://github.com/gabriel-v/kubric), see [original](https://github.com/google-research/kubric)
- BlenderGIS: [own fork](https://github.com/gabriel-v/BlenderGIS), see [original](https://github.com/domlysz/BlenderGIS)
