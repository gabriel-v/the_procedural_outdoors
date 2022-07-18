import kubric as kb
import os
from multiprocessing import Process
import logging
import pathlib

import bpy
from kubric.renderer.blender import Blender

from .utils import blend_append_object
from .utils import make_active_object
from .utils import pre_init_blender
from .utils import save_blend
from . import settings

log = logging.getLogger(__name__)

GEOMETRY_DUMMY_CUBE_NAME = 'geometry_nodes_container_cube'
GEOMETRY_TMP_FILE = 'output/tmp-saved-geometry.blend'


def new_geometry_modifier(object_name, modifier_name, node_group_name, args_dict=dict(),
                          show_viewport=True, toggle_inputs=[]):
    log.info('adding new geometry modifier obj = %s type = %s ...', object_name, node_group_name)
    mod = bpy.data.objects[object_name].modifiers.new(modifier_name, 'NODES')
    mod.node_group = bpy.data.node_groups[node_group_name]
    for key, value in args_dict.items():
        mod[key] = value

        # as per https://developer.blender.org/T87006
        bpy.data.objects[object_name].update_tag()

    mod.show_viewport = show_viewport
    for input_to_toggle in toggle_inputs:
        prop_path = '["' + input_to_toggle + '"]'
        bpy.ops.object.geometry_nodes_input_attribute_toggle(
            prop_path=prop_path,
            modifier_name=mod.name,
        )
    return mod


# This doesn't work as expected (it clones the Universe)
# def import_geometry_from_file(blend_path, node_name):
#     # section = "Node Groups"
#     section = "NodeTree"
#     log.info("Importing Geometry Nodes from file: %s/%s/%s ...", blend_path.name, section, node_name)
#     filepath  = str(blend_path / section / node_name)
#     directory = str(blend_path / section) + '/'
#
#     log.info("bpy.ops.wm.append( filepath='%s', filename='%s', directory='%s')",
#              filepath, node_name, directory)
#     ap_rv = bpy.ops.wm.append(
#         filepath=filepath,
#         filename=node_name,
#         directory=directory,
#         set_fake=False,
#         use_recursive=False,
#         do_reuse_local_id=False,
#         active_collection=False,
#     )
#
#     # immediately delete the created collection, since we only want the node tree
#     collection = bpy.data.collections.get('Appended Data')
#     for obj in collection.objects:
#         bpy.data.objects.remove(obj, do_unlink=True)
#     bpy.data.collections.remove(collection)


def import_geometry_cube(blend_path):
    log.info('importing geometry cube container from  %s...', blend_path)
    cube = blend_append_object(blend_path, GEOMETRY_DUMMY_CUBE_NAME)
    cube.select_set(True)
    cube.hide_render = True
    cube.hide_viewport = True


def save_geometry(original_path, destination_path, skip_if_missing=True):
    """Save all geometry classes on a fresh cube and store it in a blend file.

    This is needed because Blender won't let you append over a NodeTree without
    cloning over the entire Universe, with all related objects and textures.

    https://blender.stackexchange.com/questions/256669/how-can-i-append-geometry-node-objects-from-the-asset-browser-without-spilling-s

    Workaround:
        - go through all the node groups and add them to a dummy Cube
        - delete all objects that aren't that Cube
        - import Cube later and it should have no extra data
    """

    log.info('saving geometry from %s into %s', original_path, destination_path)
    if skip_if_missing and not pathlib.Path(original_path).is_file():
        log.info('skipping save_geometry()')
        return
    temp_path = GEOMETRY_TMP_FILE
    # use subprocess to run each function, because we want separate bpy imports
    # (and so we get separate blender windows with fresh entries)
    p = Process(target=_save_geometry_1, args=(original_path, temp_path, skip_if_missing))
    p.start()
    p.join()
    assert p.exitcode == 0

    p = Process(target=_save_geometry_2, args=(temp_path, destination_path, skip_if_missing))
    p.start()
    p.join()
    assert p.exitcode == 0
    try:
        os.unlink(temp_path)
    except Exception:
        pass


def _save_geometry_1(original_path, destination_path, skip_if_missing=True):
    if skip_if_missing and not pathlib.Path(original_path).is_file():
        log.info('skipping _save_geometry_1()')
        return
    log.info('running _save_geometry_1()')

    scene = kb.Scene(resolution=(settings.RESOLUTION_X, settings.RESOLUTION_X),
                     frame_start=1, frame_end=settings.MAX_FRAMES)
    renderer = Blender(
        scene, custom_scene=original_path, custom_scene_shading=True,
        adaptive_sampling=True, samples_per_pixel=settings.SAMPLES_PER_PIXEL,
    )

    pre_init_blender(renderer)

    cube_name = GEOMETRY_DUMMY_CUBE_NAME
    # before creating a new cube, let's delete the old one!
    for obj in bpy.data.objects:
        if obj.name == GEOMETRY_DUMMY_CUBE_NAME:
            log.info('DELETE OLD CUBE --  %s', obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

    scene += kb.Cube(name=cube_name, scale=(1, 1, 1), position=(0, 0, 0))

    with make_active_object(cube_name) as cube:
        cube.hide_render = True
        cube.hide_viewport = True

        already_added = set()
        for node_group in bpy.data.node_groups:
            # for each landmap item, set Geometry modifier
            if node_group.name in already_added:
                log.info('skipping save of duplicate %s', node_group.name)
                continue
            already_added.add(node_group.name)
            mod = cube.modifiers.new('geometry_wrapper_' + node_group.name, 'NODES')
            mod.node_group = bpy.data.node_groups[node_group.name]

        # immediately delete the created objects, since we *really* only want the cube
        for obj in bpy.data.objects:
            if obj.name != GEOMETRY_DUMMY_CUBE_NAME:
                log.info('DELETE  %s', obj.name)
                bpy.data.objects.remove(obj, do_unlink=True)
            else:
                log.info('KEEP %s', obj.name)

    save_blend(renderer, destination_path)


def _save_geometry_2(original_path, destination_path, skip_if_missing=True):
    if skip_if_missing and not pathlib.Path(original_path).is_file():
        log.info('skipping _save_geometry_2()')
        return
    log.info('running _save_geometry_2()')

    scene = kb.Scene(resolution=(settings.RESOLUTION_X, settings.RESOLUTION_X),
                     frame_start=1, frame_end=settings.MAX_FRAMES)
    renderer = Blender(scene, adaptive_sampling=True, samples_per_pixel=settings.SAMPLES_PER_PIXEL)

    pre_init_blender(renderer)
    # Geo Container Cube (from storage)
    # import_object_from_file(
    #     scene,
    #     GEOMETRY_DUMMY_CUBE_NAME,
    #     pathlib.Path(original_path),
    #     GEOMETRY_DUMMY_CUBE_NAME,
    # )
    import_geometry_cube(original_path)

    save_blend(renderer, destination_path)


def make_view_culling_geonodes(sat, camera_obj):
    log.info('adding view culling...')
    # set view culling on the camera for buildings & sat
    view_culling_objects = [i.name for i in sat.values()] + ['buildings']
    if settings.CAMERA_ENABLE_VIEW_CULLING:
        # viewport culling (FIRST)

        for obj_name in view_culling_objects:
            new_geometry_modifier(
                obj_name,
                'view_culling_pre',
                'ViewFrustumCulling.v2',
                {
                    'Input_2': camera_obj,
                    # these bug out unremarkably for float/int/etc
                    # 'Input_6':  CAMERA_CLIP_END,
                },
            )
            # TODO script these default values
            # view_culling_fov = 88
            # view_culling_padding = 5

            # move camera culling modifier to first place
            bpy.ops.object.select_all(action='DESELECT')
            bpy.context.view_layer.objects.active = bpy.data.objects[obj_name]
            bpy.data.objects[obj_name].select_set(True)
            while bpy.data.objects[obj_name].modifiers[0].name != "view_culling_pre":
                bpy.ops.object.modifier_move_up(modifier="view_culling_pre")
            bpy.ops.object.select_all(action='DESELECT')

    if settings.CAMERA_ENABLE_BACKFACE_CULLING:
        # backface culling (LAST)
        for obj_name in view_culling_objects:
            new_geometry_modifier(
                obj_name,
                'view_culling_post',
                'Backface Culling',
                {
                    'Input_2': camera_obj,
                },
            )
