import os
import time
import numpy
import pandas
import math
import random
import subprocess
import logging
# import pathlib

log = logging.getLogger(__name__)

import kubric as kb
import bpy

from ..utils import save_blend
from ..utils import make_active_object
# from .utils import import_object_from_file
from .. import settings
from .. import terrain

from ..interface import SceneGeneratorInterface


PARAMS = {
    'sky_alt': {
        'min': 100,
        'max': 3500,
    },
    'sky_illum': {
        'min': 0.2,
        'max': 0.3,
    },
    'sky_sum_int': {
        'min': 0.4,
        'max': 0.7,
    },
    'sky_sun_elev': {
        'min': 0.2,
        'max': 1.4,
    },
    'sky_sun_rot': {
        'min': -3,
        'max': 3,
    },
    'sky_air_density': {
        'min': 0.2,
        'max': 1.6,
    },
    'sky_dust_density': {
        'min': 0.1,
        'max': 1.0,
    },
    'sky_ozone': {
        'min': 0.2,
        'max': 6.0,
    },

    'cloud_thickness': {
        'min': 0.05,
        'max': 0.35,
    },

    'cloud_spread': {
        'min': 0.05,
        'max': 0.32,
    },

    'cloud_seed': {
        'min': 0.1234,
        'max': 0.1235,
    },
}

for v in PARAMS.values():
    if 'def' not in v:
        v['def'] = (v['min'] + v['max']) / 2


def update_sky_texture(camera, param, stage):
    params = {k: PARAMS[k]['def'] for k in PARAMS}
    assert param in params
    p_min = PARAMS[param]['min']
    p_max = PARAMS[param]['max']
    params[param] = p_min + (p_max - p_min) * stage

    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].altitude = params['sky_alt']
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[1].default_value = \
        params['sky_illum']
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_intensity = params['sky_sum_int']
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_elevation = params['sky_sun_elev']
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_rotation = params['sky_sun_rot']
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].air_density = params['sky_air_density']
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].dust_density = params['sky_dust_density']
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].ozone_density = params['sky_ozone']

    # thickness and spread
    bpy.data.materials["procedural_clouds_shader"].node_tree.nodes["Group"].inputs[4].default_value = \
        params['cloud_thickness']
    bpy.data.materials["procedural_clouds_shader"].node_tree.nodes["Group"].inputs[5].default_value = \
        params['cloud_spread']
    # seed
    bpy.data.materials["procedural_clouds_shader"].node_tree.nodes["Group"].inputs[0].default_value = \
        params['cloud_seed']


class DemoClient(SceneGeneratorInterface):
    def __init__(self, param_key):
        self.param_key = param_key

    def generate_background_scene(self, scene):
        camera = kb.PerspectiveCamera(name="camera", position=(6, -5, 1102), look_at=(0, 0, 1100))
        scene += camera
        camera_obj = bpy.data.objects[camera.name]
        camera_obj.data.lens = settings.CAMERA_LENS
        camera_obj.data.clip_start = settings.CAMERA_CLIP_START
        camera_obj.data.clip_end = settings.CAMERA_CLIP_END
        bpy.context.scene.cycles.dicing_camera = camera_obj
        terrain.make_terrain(scene, camera_obj,
                             add_trees=settings.RENDER_TREES,
                             add_buildings=settings.RENDER_BUILDINGS)
        if not settings.RENDER_CLOUDS:
            bpy.data.objects['clouds'].hide_render = True
            bpy.data.objects['clouds'].hide_viewport = True

    def init_scene_parameters(self, scene, renderer):
        log.info('creating keyframes...')
        anim_distance = (settings.MAX_FRAMES / settings.SIMULATION_FPS) * settings.CAMERA_ANIMATION_SPEED_M_S
        anim_distance *= 2
        anim_distance += 400
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
        index_count = {
            index_count[k]: index_count[k + 1] - index_count[k]
            for k in range(0, len(index_count) - 1)
        }
        start_idx, run_len = max(index_count.items(), key=lambda t: (t[1], random.random()))
        path_point = [
            path_vertices[k][1]
            for k in range(1 + start_idx, start_idx + run_len + 1)
            if k < len(path_vertices)
        ]

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
        path_point = pandas.DataFrame(_add_nan(
            path_point,
            settings.CAMERA_ANIMATION_SPEED_M_S / settings.SIMULATION_FPS))
        path_point = path_point.interpolate(method='linear', limit_area='inside')
        path_point = [tuple(t[1]) for t in path_point.iterrows()]

        cube_height = 1
        camera_height = 6
        camera_distance = 45
        camera_delay_count = int(
            camera_distance / (
                settings.CAMERA_ANIMATION_SPEED_M_S / settings.SIMULATION_FPS
            )
        )
        assert len(path_point) > settings.MAX_FRAMES + camera_delay_count + 20
        log.info('animation camera delay count = %s', camera_delay_count)
        log.info('total point count = %s', len(path_point))
        idx_buffer = int((len(path_point) - settings.MAX_FRAMES - camera_delay_count) / 2)
        idx_buffer_min = int(idx_buffer * 0.8)
        idx_buffer_max = int(idx_buffer * 1.2)
        idx_buffer = random.randint(idx_buffer_min, idx_buffer_max)
        log.info('IDX_BUFFER = %s', idx_buffer)

        # --- render (and save the blender file)
        update_sky_texture(scene.camera, self.param_key, 0)
        for frame in range(scene.frame_start, scene.frame_end + 1):
            # path coords for frame
            log.info('frame = %s', frame)
            idx_cam = idx_buffer + frame
            x0, y0, z0 = path_point[idx_cam]
            x, y, z = path_point[idx_cam + camera_delay_count]

            z0 += camera_height
            z += camera_height / 2.7
            z += cube_height

            scene.camera.position = (x0, y0, z0)
            scene.camera.look_at((x, y, z))

            scene.camera.keyframe_insert("position", frame)
            scene.camera.keyframe_insert("quaternion", frame)

        save_blend(renderer, pack=True)
        subprocess.check_call('rm -rf output/pics/ || true', shell=True)
        os.makedirs('output/pics/segmentation', exist_ok=True)

    def render(self, scene, renderer):
        for frame in range(scene.frame_start, scene.frame_end + 1):
            update_sky_texture(scene.camera, self.param_key, frame / (scene.frame_end + 1))

            # render and post-process
            log.info('starting render....')
            t0 = time.time()
            data_stack = renderer.render(
                frames=[frame],
                return_layers=(
                    "rgba", "depth", "segmentation", "normal",
                ),
            )
            t1 = time.time()
            dt = round((t1 - t0), 2)
            _frame_render_time = dt
            log.info(f""" render done! {dt} sec/frame
                    ==============================
                    =                            =
                    =         RENDER SPEED       =
                    =          {dt}           =
                    =          sec/frame         =
                    =                            =
                    ==============================
                    """)

            log.info('started output...')

            if frame < scene.frame_start + 10 or frame % 10 == 0:
                kb.write_image_dict(data_stack, kb.as_path("output/pics/"), max_write_threads=6)

        kb.write_image_dict(data_stack, kb.as_path("output/pics/"), max_write_threads=6)

    def frame_callback(self, scene, render_data=None):
        pass
