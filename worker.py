# Copyright 2022 The Kubric Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import pathlib

import kubric as kb
from kubric.renderer.blender import Blender as KubricRenderer
from kubric.core.assets import UndefinedAsset
from kubric.core.objects import FileBasedObject

logging.basicConfig(level="INFO")
CUBE_BG = "cube/background.blend"
CUBE_FG = pathlib.Path("cube/cube.blend")


# --- create scene and attach a renderer to it
scene = kb.Scene(resolution=(666, 666))
renderer = KubricRenderer(scene, custom_scene=CUBE_BG, custom_scene_shading=True,
                          adaptive_sampling=True, samples_per_pixel=16)

# --- populate the scene with objects, lights, cameras
# scene += kb.Cube(name="floor", scale=(10, 10, 0.1), position=(0, 0, -0.1))
# scene += kb.Sphere(name="ball", scale=1, position=(0, 0, 1.))
# scene += kb.DirectionalLight(name="sun", position=(-1, -0.5, 3),
#                              look_at=(0, 0, 0), intensity=1.5)
scene += kb.PerspectiveCamera(name="camera", position=(6, -5, -5),
                              look_at=(0, 0, 0))

scene += kb.FileBasedObject(
    name="Cube",
    position=(0, 0, 0.0),
    static=True, #  background=True,
    simulation_filename=None,
    render_filename=str(CUBE_FG),
    render_import_kwargs={
        "filepath": str(CUBE_FG / "Object" / "Cube"),
        "directory": str(CUBE_FG / "Object"),
        "filename": "Cube",
    })


GOOGLE_20 = pathlib.Path("/data/predeal1/google/tren/20/google-20-tren.blend")
GOOGLE_20_OBJNAME = "EXPORT_GOOGLE_SAT_WM"
scene += kb.FileBasedObject(
    name=GOOGLE_20_OBJNAME,
    position=(0, 0, 0.0),
    static=True, # background=True,
    simulation_filename=None,
    render_filename=str(GOOGLE_20),
    render_import_kwargs={
        "filepath": str(GOOGLE_20 / "Object" / GOOGLE_20_OBJNAME),
        "directory": str(GOOGLE_20 / "Object"),
        "filename": GOOGLE_20_OBJNAME,
    })

# --- render (and save the blender file)
renderer.save_state("output/helloworld.blend")
frame = renderer.render_still()

# --- save the output as pngs
kb.write_png(frame["rgba"], "output/helloworld.png")
kb.write_palette_png(frame["segmentation"], "output/helloworld_segmentation.png")
scale = kb.write_scaled_png(frame["depth"], "output/helloworld_depth.png", 1000)
logging.info("Depth scale: %s", scale)
