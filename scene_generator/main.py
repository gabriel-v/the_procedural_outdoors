import sys
import time
import subprocess
import logging
# import pathlib

log = logging.getLogger(__name__)

import kubric as kb
from kubric.renderer.blender import Blender

from .utils import pre_init_blender
# from .utils import import_object_from_file
from .utils import load_addons
from . import geometry
from . import settings

# from .clients.dataset import DatasetClient as Client
from .clients.demo import DemoClient as Client


def render_main(param_key):
    CUBE_BG = "cube/background.blend"
# --- create scene and attach a renderer to it
    scene = kb.Scene(resolution=(settings.RESOLUTION_X, settings.RESOLUTION_Y), frame_start=1,
                     frame_end=settings.MAX_FRAMES)
    renderer = Blender(
        scene, custom_scene=CUBE_BG, custom_scene_shading=True,
        adaptive_sampling=True, samples_per_pixel=settings.SAMPLES_PER_PIXEL,
    )
    pre_init_blender(renderer)

    client = Client(param_key)

    # ### TERRAIN ####
    # ================
    t0 = time.time()
    client.generate_background_scene(scene)
    t1 = time.time()
    dt = round((t1 - t0), 2)
    log.info(f""" render done! {dt} sec/frame
            =>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            =                            =
            =         TERRAIN SPEED       =
            =          {dt}           =
            =          sec         =
            =                            =
            =<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            """)
    _terrain_gen_time = dt

    client.init_scene_parameters(scene, renderer)
    client.render(scene, renderer)

    log.info('output done!')

    log.info('making gifs...')
    subprocess.check_call('bash make-gifs.sh', shell=True, stderr=subprocess.DEVNULL)

    kb.done()


def main():
    load_addons()
    geometry.save_geometry(settings.GEOMETRY_INPUT_FILE, settings.GEOMETRY_SAVE_FILE)

    if len(sys.argv) > 1:
        param_key = sys.argv[1]
    else:
        param_key = 'cloud_seed'
    render_main(param_key)
