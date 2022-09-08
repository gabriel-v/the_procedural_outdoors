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
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_intensity = random.uniform(0.4, 0.7)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_elevation = random.uniform(0.19, 1.4)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_rotation = random.uniform(-3.141, 3.141)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].air_density = random.uniform(0.2, 1.6)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].dust_density = random.uniform(0.1, 1.)
        bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].ozone_density = random.uniform(0.2, 6)

    # thickness and spread
    bpy.data.materials["procedural_clouds_shader"].node_tree.nodes["Group"].inputs[4].default_value = \
        random.uniform(0.05, 0.21)
    bpy.data.materials["procedural_clouds_shader"].node_tree.nodes["Group"].inputs[5].default_value = \
        random.uniform(0.05, 0.18)
    # seed
    bpy.data.materials["procedural_clouds_shader"].node_tree.nodes["Group"].inputs[0].default_value = \
        random.uniform(0.01, 0.99)


class DatasetClient(SceneGeneratorInterface):
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
        anim_distance += 500
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
        assert len(path_point) > settings.MAX_FRAMES + 40

        cube_height = 1
        camera_height = 8
        camera_distance = 45
        camera_delay_count = int(
            camera_distance / (
                settings.CAMERA_ANIMATION_SPEED_M_S / settings.SIMULATION_FPS
            )
        )
        log.info('animation camera delay count = %s', camera_delay_count)
        log.info('total point count = %s', len(path_point))
        idx_buffer = 30
        # frame_jump_multiplier = int(((len(path_point) - camera_delay_count - idx_buffer * 3)
        #                             / settings.MAX_FRAMES) * 0.9)  # noqa
        # assert frame_jump_multiplier >= 1
        frame_jump_multiplier = 1
        log.info('frame jump multiplier = %s', frame_jump_multiplier)

        # --- render (and save the blender file)
        update_sky_texture('N', bpy.data.objects[scene.camera.name])
        for frame in range(scene.frame_start, scene.frame_end + 1):
            # path coords for frame
            log.info('frame = %s', frame)
            idx_cam = idx_buffer + frame_jump_multiplier * frame
            x0, y0, z0 = path_point[idx_cam]
            x, y, z = path_point[idx_cam + camera_delay_count]

            z0 += camera_height
            z += camera_height / 2.7
            z += cube_height

            # scene look randomization
            RANDOM_AMOUNT = 8
            x0 += random.uniform(-RANDOM_AMOUNT, RANDOM_AMOUNT)
            y0 += random.uniform(-RANDOM_AMOUNT, RANDOM_AMOUNT)
            z0 += random.uniform(0, RANDOM_AMOUNT / 2)

            x += random.uniform(-RANDOM_AMOUNT / 2, RANDOM_AMOUNT / 2)
            y += random.uniform(-RANDOM_AMOUNT / 2, RANDOM_AMOUNT / 2)
            z += random.uniform(0, RANDOM_AMOUNT / 3)

            scene.camera.position = (x0, y0, z0)
            scene.camera.look_at((x, y, z))

            scene.camera.keyframe_insert("position", frame)
            scene.camera.keyframe_insert("quaternion", frame)
            pass

        save_blend(renderer, pack=True)
        subprocess.check_call('rm -rf output/pics/ || true', shell=True)
        os.makedirs('output/pics/segmentation', exist_ok=True)

    def render(self, scene, renderer):
        for frame in range(scene.frame_start, scene.frame_end + 1):
            camera = bpy.data.objects[scene.camera.name]
            update_sky_texture('N', camera)

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

            log.info('started post-processing...')
            # --- Postprocessing
            # kb.compute_visibility(data_stack["segmentation"], scene.assets)
            # data_stack["segmentation-2"] = kb.adjust_segmentation_idxs(
            #     data_stack["segmentation"],
            #     scene.assets,
            #     scene.assets)

            log.info('started output...')

            kb.write_image_dict(data_stack, kb.as_path("output/pics/"), max_write_threads=6)
            for i in range(0, data_stack['segmentation'].max()):
                # palette = [[0, 0, 0], [255, 255, 255]]
                kb.file_io.multi_write_image(
                    (data_stack['segmentation'] == i).astype(numpy.uint32),
                    "output/pics/segmentation/item_" + str(i) + "_{:05d}.png",
                    write_fn=kb.write_palette_png,
                    max_write_threads=6,
                    # palette=palette,
                )
            kb.file_io.multi_write_image(
                (data_stack['segmentation'] == 12).astype(numpy.uint32),
                "output/pics/rails_segmentation" + "_{:05d}.png",
                write_fn=kb.write_palette_png,
                max_write_threads=6,
                # palette=palette,
            )
        kb.file_io.write_json(filename="output/pics/camera.json", data=kb.get_camera_info(scene.camera))
        kb.file_io.write_json(filename="output/pics/metadata.json", data=kb.get_scene_metadata(scene))
        kb.file_io.write_json(filename="output/pics/object.json", data=kb.get_instance_info(scene))

    def frame_callback(self, scene, render_data=None):
        pass
