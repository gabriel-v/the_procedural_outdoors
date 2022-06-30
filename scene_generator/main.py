import numpy
import pandas
import math
import random
import subprocess
import logging
import pathlib

log = logging.getLogger(__name__)

import kubric as kb
from kubric.renderer.blender import Blender
import bpy

from .utils import pre_init_blender
from .utils import save_blend
from .utils import make_active_object
from .utils import import_object_from_file
from .utils import load_addons
from . import geometry
from . import settings
from . import terrain


def update_sky_texture(sky_texture='P', camera=None):
    if sky_texture == 'P':
        # works on both rendering engines
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sky_type = 'PREETHAM'
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].turbidity = random.uniform(2.5, 6)
        bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[1].default_value = 1
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_direction = (
            random.uniform(-1, 1),
            random.uniform(-1, 1),
            random.uniform(0, 1),
        )
    elif sky_texture == 'N':
        # only works on raytrace engine
        if camera:
            bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].altitude = camera.position[2]
        bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[1].default_value = \
            random.uniform(0.2, 0.3)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_intensity = random.uniform(0.4, 0.8)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_elevation = random.uniform(0.19, 1.4)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_rotation = random.uniform(-3.141, 3.141)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].air_density = random.uniform(0.2, 1.6)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].dust_density = random.uniform(0.1, 1.)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].ozone_density = random.uniform(0.2, 6)


def render_main():
    CUBE_BG = "cube/background.blend"

# --- create scene and attach a renderer to it
    scene = kb.Scene(resolution=(settings.RESOLUTION_X, settings.RESOLUTION_X), frame_start=1,
                     frame_end=settings.MAX_FRAMES)
    renderer = Blender(
        scene, custom_scene=CUBE_BG, custom_scene_shading=True,
        adaptive_sampling=True, samples_per_pixel=settings.SAMPLES_PER_PIXEL,
    )

    pre_init_blender(renderer)

# #### OBJECTS #####
# ============

# pos = .object.matrix_world.to_translation()
    CUBE_FG = pathlib.Path("cube/cube.blend")
    cube = import_object_from_file(scene, "Cube0", CUBE_FG, "Cube")
    cube.position = (0, 0, 1100)

    cube_light = kb.PointLight(name="cube_light", position=(0, 0, 1100), intensity=6666)
    scene += cube_light

# ### CAMERA ####
# ============
    camera = kb.PerspectiveCamera(name="camera", position=(6, -5, 1102),
                                  look_at=(0, 0, 1100))
    scene += camera
    camera_obj = bpy.data.objects[camera.name]
    camera_obj.data.lens = settings.CAMERA_LENS
    camera_obj.data.clip_start = settings.CAMERA_CLIP_START
    camera_obj.data.clip_end = settings.CAMERA_CLIP_END
    bpy.context.scene.cycles.dicing_camera = camera_obj

    # ### TERRAIN ####
    # ================
    terrain.make_terrain(scene, camera_obj, add_trees=False)

# --- populate the scene with objects, lights, cameras
# scene += kb.Cube(name="floor", scale=(10, 10, 0.1), position=(0, 0, -0.1))
# scene += kb.Sphere(name="ball", scale=1, position=(0, 0, 1.))
# scene += kb.DirectionalLight(name="sun", position=(-1, -0.5, 3),
#                              look_at=(0, 0, 0), intensity=1.5)

    log.info('creating keyframes...')
    anim_distance = (settings.MAX_FRAMES / settings.SIMULATION_FPS) * settings.CAMERA_ANIMATION_SPEED_M_S
    anim_distance *= 2
    anim_distance += 300
    animation_path = 'rails_center'
    with make_active_object(animation_path):
        path_vertices = [
            (d.index, (d.co.xyz.to_tuple()))
            for d in bpy.context.active_object.data.vertices
            if math.sqrt(
                d.co.xyz.to_tuple()[0]**2 + d.co.xyz.to_tuple()[1]**2
            ) < anim_distance
        ]
    index_count = [
        i
        for i, (x, y) in enumerate(
            zip([a[0] for a in path_vertices[:-1]],
                [a[0] for a in path_vertices[1:]])
        )
        if x + 1 != y
    ]
    index_count = [0] + index_count + [len(path_vertices)]
    index_count = {index_count[k]: index_count[k + 1] - index_count[k]
                   for k in range(0, len(index_count) - 1)}
    start_idx, run_len = max(index_count.items(), key=lambda t: (t[1], random.random()))
    path_point = [path_vertices[k][1]
                  for k in range(1 + start_idx, start_idx + run_len + 1)
                  if k < len(path_vertices)]

    def _3d_dist(point, next_point):
        return math.sqrt(
            (point[0] - next_point[0])**2
            + (point[1] - next_point[1])**2  # noqa
            + (point[2] - next_point[2])**2  # noqa
        )

    def _add_nan(points, avg_dist=1):
        log.info('adding NaN to %s points, interp dist %s', len(points), avg_dist)
        for point_id in range(0, len(points) - 1):
            point = points[point_id]
            next_point = points[point_id + 1]
            next_point_dist = _3d_dist(point, next_point)
            yield point
            yield from [(numpy.nan, numpy.nan, numpy.nan)] * int(next_point_dist / avg_dist)
        yield points[-1]

    start_to_end_dist = _3d_dist(path_point[0], path_point[-1])
    path_point = pandas.DataFrame(_add_nan(path_point,
                                           settings.CAMERA_ANIMATION_SPEED_M_S / settings.SIMULATION_FPS))
    path_point = path_point.interpolate(method='linear', limit_area='inside')
    path_point = [tuple(t[1]) for t in path_point.iterrows()]
    assert len(path_point) > settings.MAX_FRAMES + 40
    path_mid_idx_offset = int((len(path_point) - settings.MAX_FRAMES) / 2 + 15)

    cube_height = 1
    camera_height = 1.8
    camera_distance = 20
    camera_delay_count = int(
        camera_distance / (
            settings.CAMERA_ANIMATION_SPEED_M_S / settings.SIMULATION_FPS
        )
    )
    log.info('animation camera delay steps = %s', camera_delay_count)
    if camera_delay_count > path_mid_idx_offset:
        log.warning('not enough space in path for camera delay!')
        camera_delay_count = path_mid_idx_offset
    if camera_delay_count < 1:
        log.warning('zero delay count! reset to 1')
        camera_delay_count = 1

    for frame in range(scene.frame_start, scene.frame_end + 1):
        # path coords for frame
        x0, y0, z0 = path_point[frame + path_mid_idx_offset - camera_delay_count]
        x, y, z = path_point[frame + path_mid_idx_offset]
        x1, y1, z1 = path_point[frame + path_mid_idx_offset + 1]

        z0 += camera_height
        z += cube_height
        z1 += cube_height

        scene.camera.position = (x0, y0, z0)
        scene.camera.look_at((x, y, z))

        scene.camera.keyframe_insert("position", frame)
        scene.camera.keyframe_insert("quaternion", frame)

        cube.position = (x, y, z)
        cube.look_at((x1, y1, z1))
        cube.keyframe_insert("position", frame)
        cube.keyframe_insert("quaternion", frame)

        cube_light.position = (x + random.uniform(-0.1, 0.1),
                               y + random.uniform(-0.1, 0.1),
                               z + random.uniform(-0.1, 0.1))
        cube_light.keyframe_insert("position", frame)

    update_sky_texture('N', camera)
    # --- render (and save the blender file)
    save_blend(renderer, pack=True)

# render and post-process
    log.info('starting render....')
    data_stack = renderer.render(
        return_layers=(
            "rgba", "depth", "segmentation", "normal",
        ),
    )
    log.info('render done!')

    log.info('started output...')
    subprocess.check_call('rm -rf output/pics/ || true', shell=True)
    kb.write_image_dict(data_stack, kb.as_path("output/pics/"), max_write_threads=6)
    kb.file_io.write_json(filename="output/pics/camera.json", data=kb.get_camera_info(scene.camera))
    kb.file_io.write_json(filename="output/pics/metadata.json", data=kb.get_scene_metadata(scene))
    kb.file_io.write_json(filename="output/pics/object.json", data=kb.get_instance_info(scene))
    log.info('output done!')

    log.info('making gifs...')
    subprocess.check_call('bash make-gifs.sh', shell=True,
                          stderr=subprocess.DEVNULL)

    kb.done()


def main():
    load_addons()
    geometry.save_geometry(settings.GEOMETRY_INPUT_FILE, settings.GEOMETRY_SAVE_FILE)

    # EXTRA_GEOMETRY_FUNC_FILE = "/data/xxx.blend"
    # save_geometry(EXTRA_GEOMETRY_FUNC_FILE, GEOMETRY_SAVE_FILE_2)

    render_main()
