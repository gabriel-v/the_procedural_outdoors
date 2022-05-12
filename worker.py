import contextlib
import random
import os
from multiprocessing import Process
import subprocess
import logging
import pathlib
import importlib
import datetime


class DeltaTimeFormatter(logging.Formatter):
    def format(self, record):
        duration = datetime.datetime.utcfromtimestamp(record.relativeCreated / 1000)
        record.delta = duration.strftime("%H:%M:%S")
        return super().format(record)


# add custom formatter to root logger
handler = logging.StreamHandler()
LOGFORMAT = '+%(delta)s %(funcName)-9s() %(levelname)-9s: %(message)s'
fmt = DeltaTimeFormatter(LOGFORMAT)
handler.setFormatter(fmt)
logging.getLogger().addHandler(handler)
log = logging.getLogger(__name__)
log.setLevel('DEBUG')

# need these down here to respect my logging config
import kubric as kb
from kubric.renderer.blender import Blender
import bpy

RANDOM_TREE_COUNT = 20

CAMERA_LENS = 33.3
CAMERA_CLIP_START = 0.1
CAMERA_CLIP_END = 60000
SAMPLES_PER_PIXEL = 16
RENDER_TIME_LIMIT = 222
# RENDER_TILE_SIZE = 4096
RENDER_THREAD_COUNT = 6

CAMERA_ENABLE_VIEW_CULLING = False
CAMERA_ENABLE_BACKFACE_CULLING = False

MAX_FRAMES = 10
# MAX_FRAMES = 1
RESOLUTION_X = 666

MAIN_BLEND_FILE = "output/trains.blend"

GEOMETRY_DUMMY_CUBE_NAME = 'geometry_nodes_container_cube'

GEOMETRY_INPUT_FILE = 'output/trains.blend'
# GEOMETRY_INPUT_FILE = 'cube/tmp/geometry.blend'
GEOMETRY_SAVE_FILE = 'cube/geometry.blend'
# GEOMETRY_SAVE_FILE_2 = 'cube/saved-geometry-2.blend'
GEOMETRY_TMP_FILE = 'output/tmp-saved-geometry.blend'


def update_sky_texture():

    # works on both rendering engines
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sky_type = 'PREETHAM'
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].turbidity = random.uniform(2.5, 6)
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[1].default_value = 1
    bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_direction = (
        random.uniform(-1, 1),
        random.uniform(-1, 1),
        random.uniform(0, 1),
    )

    # for the other type
    # bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].altitude = camera.position[2]


def new_geometry_modifier(object_name, modifier_name, node_group_name, args_dict,
                          show_viewport=True):
    log.info('adding new geometry modifier obj = %s type = %s ...', object_name, node_group_name)
    mod = bpy.data.objects[object_name].modifiers.new(modifier_name, 'NODES')
    mod.node_group = bpy.data.node_groups[node_group_name]
    for key, value in args_dict.items():
        mod[key] = value

        # as per https://developer.blender.org/T87006
        bpy.data.objects[object_name].update_tag()

    mod.show_viewport = show_viewport
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


def blend_append_object(blend_path, obj_name, active_collection=False):
    blend_path = pathlib.Path(blend_path)
    section = "Object"
    log.info("Appending Blender Object from file: %s/%s ...", blend_path.name, obj_name)
    filepath = str(blend_path / section / obj_name)
    directory = str(blend_path / section) + '/'

    log.debug("bpy.ops.wm.append( filepath='%s', filename='%s', directory='%s')",
              filepath, obj_name, directory)
    bpy.ops.wm.append(
        filepath=filepath,
        filename=obj_name,
        directory=directory,
        set_fake=False,
        use_recursive=False,
        do_reuse_local_id=False,
        active_collection=active_collection,
    )

    cube = bpy.data.objects[obj_name]
    return cube

    # # immediately delete the created collection, since we only want the node tree
    # collection = bpy.data.collections.get('Appended Data')
    # for obj in collection.objects:
    #     bpy.data.objects.remove(obj, do_unlink=True)
    # bpy.data.collections.remove(collection)


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

    scene = kb.Scene(resolution=(RESOLUTION_X, RESOLUTION_X), frame_start=1, frame_end=MAX_FRAMES)
    renderer = Blender(
        scene, custom_scene=original_path, custom_scene_shading=True,
        adaptive_sampling=True, samples_per_pixel=SAMPLES_PER_PIXEL,
    )

    pre_init_blender(renderer)

    cube_name = GEOMETRY_DUMMY_CUBE_NAME
    # before creating a new cube, let's delete the old one!
    for obj in bpy.data.objects:
        if obj.name == GEOMETRY_DUMMY_CUBE_NAME:
            log.info('DELETE OLD CUBE --  %s', obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

    scene += kb.Cube(name=cube_name, scale=(1, 1, 1), position=(0, 0, 0))
    cube = bpy.data.objects[cube_name]
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)
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

    scene = kb.Scene(resolution=(RESOLUTION_X, RESOLUTION_X), frame_start=1, frame_end=MAX_FRAMES)
    renderer = Blender(scene, adaptive_sampling=True, samples_per_pixel=SAMPLES_PER_PIXEL)

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


def save_blend(renderer, destination=MAIN_BLEND_FILE, pack=False):
    log.info('saving %s', destination)
    if pack:
        bpy.ops.file.pack_all()
    renderer.save_state(destination)


def pre_init_blender(renderer):
    """ Set up blender after kubric renderer instantiation with extra settings """
    log.info('init settings...')
    bpy.context.scene.render.engine = 'CYCLES'
    # bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    bpy.context.scene.cycles.feature_set = 'EXPERIMENTAL'
    bpy.context.scene.view_settings.look = 'Medium High Contrast'
    bpy.context.scene.cycles.use_preview_denoising = True

    # https://blender.stackexchange.com/questions/230011/why-is-area-type-none-when-starting-blender-script-from-cmd
    for area_3d in [area for area in bpy.context.screen.areas if area.type == 'VIEW_3D']:
        for space_3d in area_3d.spaces:
            space_3d.lens = CAMERA_LENS
            space_3d.clip_start = CAMERA_CLIP_START
            space_3d.clip_end = CAMERA_CLIP_END

    if os.getenv("KUBRIC_USE_GPU", "False").lower() in ("true", "1", "t"):
        log.info('enable gpu for main render...')
        renderer.use_gpu = True
        bpy.context.preferences.addons["cycles"].preferences.get_devices()
        devices_used = [d.name for d in bpy.context.preferences.addons["cycles"].preferences.devices
                        if d.use]
        log.warning("\n =========== NVIDIA\n============>>> Using the following GPU Device(s): %s",
                    devices_used)

    bpy.context.scene.render.threads_mode = 'FIXED'
    bpy.context.scene.render.threads = RENDER_THREAD_COUNT
    # bpy.context.scene.cycles.tile_size = RENDER_TILE_SIZE
    bpy.context.scene.cycles.debug_use_spatial_splits = True
    bpy.context.scene.cycles.debug_bvh_time_steps = 1
    bpy.context.scene.cycles.max_subdivisions = 6
    bpy.context.scene.cycles.offscreen_dicing_scale = 44
    bpy.context.scene.cycles.max_bounces = 6
    bpy.context.scene.cycles.caustics_refractive = False
    bpy.context.scene.cycles.caustics_reflective = False
    # bpy.context.scene.cycles.use_fast_gi = True
    # bpy.context.scene.render.use_motion_blur = True
    bpy.context.scene.cycles.time_limit = RENDER_TIME_LIMIT
    bpy.context.scene.cycles.samples = SAMPLES_PER_PIXEL
    bpy.context.scene.cycles.preview_samples = SAMPLES_PER_PIXEL


def cut_object(target_id, cutout_id, exact=False, hole_tolerant=True, solidify=False):
    log.info('cutting %s out of %s', cutout_id, target_id)
    # bpy.data.objects[target_id].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[target_id]

    bpy.ops.object.modifier_add(type='BOOLEAN')
    bpy.context.object.modifiers["Boolean"].operation = 'DIFFERENCE'
    bpy.context.object.modifiers["Boolean"].object = bpy.data.objects[cutout_id]

    if exact:
        bpy.context.object.modifiers["Boolean"].solver = 'EXACT'
        bpy.context.object.modifiers["Boolean"].use_self = False
        bpy.context.object.modifiers["Boolean"].use_hole_tolerant = hole_tolerant
    else:
        bpy.context.object.modifiers["Boolean"].solver = 'FAST'
        bpy.context.object.modifiers["Boolean"].double_threshold = 0

    bpy.ops.object.modifier_apply(modifier="Boolean")


def import_object_from_file(scene, new_name, orig_filename, orig_name,
                            convert_to_mesh=False, triangulate=False,
                            add_bbox=False,
                            bbox_scale_z=None, bbox_scale_xy=1,
                            get_geo_extents=False, convert_to_curve=False,
                            shrinkwrap_to_planes=None, exclude_from_scene=False,
                            subsurf_levels=None):
    """save is important to check for bad objects"""

    log.info("Importing object from file: %s -> %s ...", orig_name, new_name)
    cube = kb.FileBasedObject(
        name=new_name,
        position=(0, 0, 0.0),
        static=True,
        # background=True,
        simulation_filename=None,
        render_filename=str(orig_filename),
        render_import_kwargs={
            "filepath": str(orig_filename / "Object" / orig_name),
            "directory": str(orig_filename / "Object"),
            "filename": orig_name,
        })
    if not exclude_from_scene:
        scene += cube

    bpy.data.objects[new_name].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[new_name]

    if get_geo_extents:
        _get_geo_extents()

    if convert_to_mesh:
        log.info('%s: Convert into MESH', bpy.context.object.name)
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

    if subsurf_levels:
        _subsurf_modif(subsurf_levels)

    if convert_to_curve:
        log.info('%s: Convert into CURVE', bpy.context.object.name)
        bpy.ops.object.convert(target='CURVE')

    if shrinkwrap_to_planes:
        _shrinkwrap_z(shrinkwrap_to_planes)

    if add_bbox:
        log.info('%s: Adding BBOX', bpy.context.object.name)
        obj = bpy.data.objects[new_name]
        # create a cube for the bounding box
        bpy.ops.mesh.primitive_cube_add()
        # our new cube is now the active object, so we can keep track of it in a variable:
        bound_box = bpy.context.active_object

        # copy transforms to bbox
        bound_box.name = new_name + '__bbox'
        bound_box.hide_render = True
        bound_box.hide_viewport = True
        bound_box.hide_select = True
        bound_box.dimensions = obj.dimensions
        bound_box.location = obj.location
        bound_box.rotation_euler = obj.rotation_euler
        if bbox_scale_z:
            bpy.data.objects[new_name].select_set(False)
            bpy.data.objects[bound_box.name].select_set(True)
            bpy.context.view_layer.objects.active = bpy.data.objects[bound_box.name]
            bpy.ops.transform.resize(value=(bbox_scale_xy, bbox_scale_xy, bbox_scale_z),
                                     orient_type='GLOBAL',
                                     orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                     orient_matrix_type='GLOBAL',
                                     constraint_axis=(False, False, True),
                                     mirror=False,
                                     use_proportional_edit=False,
                                     proportional_edit_falloff='SMOOTH',
                                     proportional_size=1,
                                     use_proportional_connected=False,
                                     use_proportional_projected=False)
            bpy.data.objects[bound_box.name].select_set(False)

        bpy.data.objects[new_name].select_set(True)
        bpy.context.view_layer.objects.active = bpy.data.objects[new_name]

    if triangulate:
        log.info('%s: TRIANGULATE', bpy.context.object.name)
        bpy.ops.object.mode_set(mode='EDIT')      # switch to mesh edit mode
        bpy.ops.mesh.select_all(action='SELECT')  # select all faces
        bpy.ops.mesh.quads_convert_to_tris()      # triangulate
        bpy.ops.object.mode_set(mode='OBJECT')    # back to object mode

    bpy.data.objects[new_name].select_set(False)

    return cube


def _shrinkwrap_z(plane_ids):
    for plane_id in plane_ids:
        log.info('%s: Applying SHRINKWRAP onto %s', bpy.context.object.name, plane_id)
        bpy.ops.object.modifier_add(type='SHRINKWRAP')
        bpy.context.object.modifiers["Shrinkwrap"].target = bpy.data.objects[plane_id]
        bpy.context.object.modifiers["Shrinkwrap"].wrap_mode = 'ABOVE_SURFACE'
        bpy.context.object.modifiers["Shrinkwrap"].wrap_method = 'PROJECT'
        bpy.context.object.modifiers["Shrinkwrap"].use_project_z = True
        bpy.context.object.modifiers["Shrinkwrap"].use_negative_direction = True
        bpy.context.object.modifiers["Shrinkwrap"].use_apply_on_spline = True
        bpy.ops.object.modifier_apply(modifier="Shrinkwrap")


def _subsurf_modif(levels):
    log.info('%s: Applying SUBSURF levels= %s', bpy.context.object.name, levels)
    bpy.ops.object.modifier_add(type='SUBSURF')
    bpy.context.object.modifiers["Subdivision"].subdivision_type = 'CATMULL_CLARK'
    bpy.context.object.modifiers["Subdivision"].levels = levels
    bpy.context.object.modifiers["Subdivision"].render_levels = levels
    bpy.context.object.modifiers["Subdivision"].show_only_control_edges = False
    bpy.ops.object.modifier_apply(modifier="Subdivision")


def _decimate_dissolve(obj):
    modifier_name = 'decimate_dissolve'
    mod = obj.modifiers.new(modifier_name, 'DECIMATE')
    mod.decimate_type = 'DISSOLVE'
    mod.angle_limit = 0.026  # 1.5 deg
    mod.use_dissolve_boundaries = False


@contextlib.contextmanager
def make_active_collection(name):
    log.info('set active collection = %s', name)
    try:
        orig_c = bpy.context.scene.collection
        layer_old_c = bpy.context.view_layer.active_layer_collection
        if name not in bpy.data.collections:
            collection = bpy.data.collections.new(name)
            orig_c.children.link(collection)
        else:
            collection = bpy.data.collections[name]

        layer_collection = bpy.context.view_layer.layer_collection.children[collection.name]
        bpy.context.view_layer.active_layer_collection = layer_collection
        yield collection
    finally:
        bpy.context.view_layer.active_layer_collection = layer_old_c


def load_random_trees_highpoly(tree_count=30):
    log.info('importing %s x hi poly trees', tree_count)
    with open('cube/tree-assets.txt', 'r') as f:
        tree_blend_files = [pathlib.Path(x.strip()) for x in f.readlines()]

    tree_blend_files = random.sample(tree_blend_files, tree_count)

    tree_id_list = []
    with make_active_collection('trees_high_poly') as c:
        for blend_path in tree_blend_files:
            tree_id = blend_path.stem.split('-')[0][6:]
            tree = blend_append_object(blend_path, tree_id, active_collection=True)
            # tree.hide_render = True
            # tree.hide_viewport = True
            tree_id_list.append(tree.name)

    return tree_id_list, c


def load_buildings(scene, sat):
    log.info('loading buildings...')
    # import buiildings last, so the shrinkwrap works over the extra-bent terrain
    import_object_from_file(
        scene,
        'buildings',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Areas:building',
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )
    obj = bpy.data.objects['buildings']
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.vertex_groups.new(name='building__top')
    obj.vertex_groups.new(name='building__side')
    obj.vertex_groups.new(name='building__wall_uv')
    obj.vertex_groups.new(name='building__top_uv')

    g1 = new_geometry_modifier(
        obj.name,
        'buildings_solidify',
        'HouseSolidify',
        {
            "Output_2_attribute_name": 'building__top',
            "Output_3_attribute_name": 'building__side',
            "Output_4_attribute_name": 'building__wall_uv',
            "Output_5_attribute_name": 'building__top_uv',
        },
    )

    # obj.hide_render = True
    # obj.hide_viewport = True

    # bpy.ops.object.modifier_apply(modifier=g1.name)
    obj.select_set(False)
    return obj


def make_sat(scene):
    log.info('importing sattelite stuff...')
    sat = {}
    GOOGLE_SAT_OBJNAME = "EXPORT_GOOGLE_SAT_WM"
    for zoom in range(15, 23):
        if zoom in [16, 19, 20, 21, 22]:
            log.warning('skipping zoom level %s because errors', zoom)
            continue
        newname = 'sat_' + str(zoom)
        oldpath = pathlib.Path(f"/data/predeal1/google/tren/{zoom}/google-{zoom}-tren.blend")
        sat[zoom] = import_object_from_file(
            scene, newname, oldpath, GOOGLE_SAT_OBJNAME,
            convert_to_mesh=True, add_bbox=True,
            # triangulate=True,
            # bbox_scale_z=2, bbox_scale_xy=0.5,
            # get_geo_extents=True,
        )
    keys = sorted(sat.keys())

    # cut the big sats in the middle
    for i in range(len(keys) - 1):
        big_obj = sat[keys[i]].name
        small_obj = sat[keys[i + 1]].name + '__bbox'
        cut_object(big_obj, small_obj, hole_tolerant=i == 0)

    for i, key in enumerate(reversed(keys)):
        # transform_z = -20 * i
        transform_z = -5 * i
        bpy.context.view_layer.objects.active = bpy.data.objects[sat[key].name]
        bpy.data.objects[sat[key].name].select_set(True)

        # take edge loop down
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.region_to_loop()
        bpy.ops.transform.translate(value=(-0, -0, transform_z),
                                    orient_axis_ortho='X',
                                    orient_type='GLOBAL',
                                    orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                    orient_matrix_type='GLOBAL',
                                    constraint_axis=(False, False, True),
                                    mirror=True, use_proportional_edit=False,
                                    proportional_edit_falloff='SMOOTH', proportional_size=1,
                                    use_proportional_connected=False,
                                    use_proportional_projected=False)
        bpy.ops.object.editmode_toggle()

        # bpy.ops.earth.curvature()
        # bpy.ops.transform.translate(value=(-0, -0, transform_z), orient_axis_ortho='X',
        #                             orient_type='GLOBAL',
        #                             orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        #                             orient_matrix_type='GLOBAL',
        #                             constraint_axis=(False, False, True),
        #                             mirror=False, use_proportional_edit=False,
        #                             proportional_edit_falloff='SMOOTH', proportional_size=1,
        #                             use_proportional_connected=False,
        #                             use_proportional_projected=False)

        bpy.data.objects[sat[key].name].select_set(False)

    # set up sat shader
    for key in sat:
        obj = bpy.data.objects[sat[key].name]
        mat = obj.active_material
        tree = bpy.data.materials[mat.name].node_tree

        # add bump node color -> height -> normals
        bump = tree.nodes.new(type="ShaderNodeBump")
        bump.location = -200, -333
        bump.inputs.get('Strength').default_value = 0.4
        bump.inputs.get('Distance').default_value = 1.5
        tree.links.new(tree.nodes["Image Texture"].outputs.get("Color"),
                       bump.inputs.get('Height'))
        tree.links.new(bump.outputs.get('Normal'),
                       tree.nodes['Principled BSDF'].inputs.get('Normal'))

        # lower specular --> 0.1 (no shiny mountains pls)
        tree.nodes["Principled BSDF"].inputs.get('Specular').default_value = 0

        # AO and mix node
        ao = tree.nodes.new(type="ShaderNodeAmbientOcclusion")
        ao.inputs[1].default_value = 200
        ao.location = -300, 300
        tree.links.new(tree.nodes["Image Texture"].outputs.get("Color"),
                       ao.inputs.get('Color'))

        math = tree.nodes.new(type="ShaderNodeMath")
        math.operation = "POWER"
        math.location = -50, 300
        math.use_clamp = True
        tree.links.new(ao.outputs.get("Color"), math.inputs[0])
        math.inputs[1].default_value = 55.5

        mix = tree.nodes.new(type="ShaderNodeMixRGB")
        mix.use_clamp = True
        mix.blend_type = "MULTIPLY"
        mix.inputs.get('Fac').default_value = 0.4
        mix.location = 150, 300

        tree.links.new(tree.nodes["Image Texture"].outputs.get("Color"),
                       mix.inputs.get('Color1'))

        tree.links.new(math.outputs.get("Value"),
                       mix.inputs.get('Color2'))

        tree.links.new(mix.outputs.get('Color'),
                       tree.nodes['Principled BSDF'].inputs.get('Base Color'))

    return sat


def import_paths(scene, sat):
    log.info('importing paths...')
    # extra stuff: paths
    import_object_from_file(
        scene,
        'path_train__1',
        pathlib.Path("/data/predeal1/google/tren/22/google-22-tren.blend"),
        '300',
        subsurf_levels=2,
    )
    import_object_from_file(
        scene,
        'path_train__2',
        pathlib.Path("/data/predeal1/google/tren/22/google-22-tren.blend"),
        '300.001',
        subsurf_levels=2,
    )

    import_object_from_file(
        scene,
        'path_car__1',
        pathlib.Path("/data/predeal1/google/tren/22/google-22-tren.blend"),
        'Bulevardul Mihail Săulescu',
        subsurf_levels=2,
    )

    import_object_from_file(
        scene,
        'roads',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Ways:highway',
        convert_to_curve=True,
        subsurf_levels=2,
        # shrinkwrap_to_plane='sat_18',
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )

    import_object_from_file(
        scene,
        'rails',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Ways:railway',
        subsurf_levels=2,
        convert_to_curve=True,
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )


def load_lowpoly_vegetation(veg_type):
    log.info('making lowpoly trees...')
    LOWPOLY_VEG_FILE = '/data/trees/turbosquid-shapepspark-lowpoly/shapespark-low-poly-plants-kit.blend'  # noqa
    LOWPOLY_OBJECT_NAMES = {
        "trees": [
            "Tree-01-1",
            "Tree-01-2",
            "Tree-01-3",
            "Tree-01-4",
            "Tree-02-1",
            "Tree-02-2",
            "Tree-02-3",
            "Tree-02-4",
            "Tree-03-1",
            "Tree-03-2",
            "Tree-03-3",
            "Tree-03-4",
        ],
    }
    tree_id_list = []
    with make_active_collection(veg_type + '_low_poly') as c:
        for obj_name in LOWPOLY_OBJECT_NAMES[veg_type]:
            tree = blend_append_object(LOWPOLY_VEG_FILE, obj_name, active_collection=True)
            # tree.hide_render = True
            # tree.hide_viewport = True
            tree_id_list.append(tree.name)

    return tree_id_list, c


def make_trees(scene, camera_obj, sat, load_highpoly=False):
    log.info('making trees...')

    if load_highpoly:
        tree_list, trees_collection = load_random_trees_highpoly(RANDOM_TREE_COUNT)
    else:
        tree_list, trees_collection = load_lowpoly_vegetation('trees')

    ret_list = []
    for zoom in sat:
        sat_obj = bpy.data.objects[sat[zoom].name]
        bpy.ops.object.duplicate(
            {"object": sat_obj,
                "selected_objects": [sat_obj]},)
        obj = bpy.data.objects[sat_obj.name + '.001']
        obj.name = sat[zoom].name + '__vegetation'
        # scene += obj
        # scene += kb.Cube(name=veg_id, scale=(1, 1, 1), position=(0, 0, 0))

        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # obj.hide_render = True
        # obj.hide_viewport = True

        log.info('adding vegetation geometry modifier on zoom level %s...', zoom)
        g1 = new_geometry_modifier(
            obj.name,
            'iarbă',
            'Iarbă',
            {
                "Input_2": camera_obj,
                "Input_3": trees_collection,
                # why should it be this simple?
                # "Input_4_use_attribute": "true",
                "Input_4_attribute_name": 'paths',
                "Input_5": sat_obj,
            },
        )
        bpy.ops.object.geometry_nodes_input_attribute_toggle(
            prop_path="[\"Input_4_use_attribute\"]",
            modifier_name=g1.name,
        )

        obj.select_set(False)
        ret_list.append(obj)
    return ret_list


def make_terrain(scene, camera_obj):
    log.info('creating terrain...')
    sat = make_sat(scene)
    keys = sorted(sat.keys())
    import_paths(scene, sat)

    # import geometry container cube
    import_geometry_cube(GEOMETRY_SAVE_FILE)
    # import_geometry_cube(GEOMETRY_SAVE_FILE_2)

    geo_mods = {}
    for zoom in sat:
        # select land obj
        bpy.context.view_layer.objects.active = bpy.data.objects[sat[zoom].name]
        bpy.data.objects[sat[zoom].name].select_set(True)

        # for each landmap item, set Geometry modifier
        geo_mods[zoom] = new_geometry_modifier(
            sat[zoom].name,
            'terrain_adjust',
            'terrain_adjust_height',
            {
                'Input_3': bpy.data.objects["rails"],
                'Input_4': bpy.data.objects["roads"]
            }
        )

        bpy.data.objects[sat[zoom].name].vertex_groups.new(name='paths')
        geo_mods[zoom]["Output_2_attribute_name"] = "paths"

        # bpy.data.objects[sat[zoom].name].vertex_groups.new(name='rails_prox')
        # geo_mods[zoom]["Output_6_attribute_name"] = "rails_prox"

        # bpy.data.objects[sat[zoom].name].vertex_groups.new(name='roads_prox')
        # geo_mods[zoom]["Output_7_attribute_name"] = "roads_prox"

        # bpy.data.objects[sat[zoom].name].vertex_groups.new(name='limit_terrain_prox')
        # geo_mods[zoom]["Output_8_attribute_name"] = "limit_terrain_prox"

        # after geometry, do a decimate with a low angle to reduce redundant faces
        _decimate_dissolve(bpy.data.objects[sat[zoom].name])

    bpy.ops.object.select_all(action='DESELECT')

    for outer_zoom, inner_zoom in zip(keys, keys[1:]):
        geo_mods[outer_zoom]['Input_5'] = bpy.data.objects[sat[inner_zoom].name]

    # apply all the sat geo mods from above, including and what-have-you
    # for zoom in sat:
    #     sat_obj = bpy.data.objects[sat[zoom].name]
    #     sat_obj.select_set(True)
    #     bpy.context.view_layer.objects.active = sat_obj

    #     for mod in sat_obj.modifiers:
    #         log.info('applying modifier %s on object %s', mod.name.encode('ascii', 'backslashreplace').decode('ascii'), sat_obj.name)  # noqa
    #         bpy.ops.object.modifier_apply(modifier=mod.name)

    #     sat_obj.select_set(False)

    building_object = load_buildings(scene, sat)

    trees = make_trees(scene, camera_obj, sat)

    # make_view_culling_geonodes(sat, camera_obj)

    # at the end, apply adaptive subdivision for all relevant objects
    # log.info('enabling adaptive subdivision...')
    # objects_for_adaptive_subdivision = \
    #     [bpy.data.objects[sat[zoom].name] for zoom in sat] + [building_object] + trees
    # enable_adaptive_subdivision(objects_for_adaptive_subdivision)

    return sat


def enable_adaptive_subdivision(object_list):
    log.info('enabling adaptive subdivision for %s objects', len(object_list))
    for obj in object_list:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_add(type='SUBSURF')
        bpy.context.object.cycles.use_adaptive_subdivision = True
        bpy.context.object.cycles.dicing_rate = 0.9
        bpy.context.object.modifiers["Subdivision"].levels = 0
        obj.select_set(False)


def make_view_culling_geonodes(sat, camera_obj):
    log.info('adding view culling...')
    # set view culling on the camera for buildings & sat
    view_culling_objects = [i.name for i in sat.values()] + ['buildings']
    if CAMERA_ENABLE_VIEW_CULLING:
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

    if CAMERA_ENABLE_BACKFACE_CULLING:
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


def load_addons():
    log.info('loading addons')
    # bpy.ops.preferences.addon_install(filepath='/addons/BlenderGIS/__init__.py')
    bpy.ops.preferences.addon_enable(module='BlenderGIS')

    print(bpy.context.preferences.addons['BlenderGIS'].preferences.demServerJson)
    # api_key = 'xxxxx'
    # if 'API_Key' not in bpy.context.preferences.addons['BlenderGIS'].preferences.demServer:
    # bpy.context.preferences.addons['BlenderGIS'].preferences.demServer += f"&API_Key={api_key}"
    bpy.ops.wm.save_userpref()


def _get_geo_extents():
    op_utils = importlib.import_module('BlenderGIS.operators.utils')
    geoscene = importlib.import_module('BlenderGIS.geoscene')
    core_proj = importlib.import_module('BlenderGIS.core.proj')

    geoscn = geoscene.GeoScene(bpy.context.scene)
    obj = bpy.context.active_object
    geo_bbox = op_utils.getBBOX.fromObj(obj).toGeo(geoscn)

    print(geo_bbox)
    print(geo_bbox.dimensions)
    print(repr(geo_bbox))

    # I love magic numbers!
    geo_bbox = core_proj.reprojBbox(geoscn.crs, 4326, geo_bbox)

    print(geo_bbox)
    print(geo_bbox.dimensions)
    print(repr(geo_bbox))


def render_main():
    CUBE_BG = "cube/background.blend"

# --- create scene and attach a renderer to it
    scene = kb.Scene(resolution=(RESOLUTION_X, RESOLUTION_X), frame_start=1, frame_end=MAX_FRAMES)
    renderer = Blender(
        scene, custom_scene=CUBE_BG, custom_scene_shading=True,
        adaptive_sampling=True, samples_per_pixel=SAMPLES_PER_PIXEL)

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
    camera_obj.data.lens = CAMERA_LENS
    camera_obj.data.clip_start = CAMERA_CLIP_START
    camera_obj.data.clip_end = CAMERA_CLIP_END
    bpy.context.scene.cycles.dicing_camera = camera_obj

    make_terrain(scene, camera_obj)

# --- populate the scene with objects, lights, cameras
# scene += kb.Cube(name="floor", scale=(10, 10, 0.1), position=(0, 0, -0.1))
# scene += kb.Sphere(name="ball", scale=1, position=(0, 0, 1.))
# scene += kb.DirectionalLight(name="sun", position=(-1, -0.5, 3),
#                              look_at=(0, 0, 0), intensity=1.5)

    log.info('creating keyframes...')
    animation_path = 'path_car__1'
    anim_height = 6
    bpy.data.objects[animation_path].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[animation_path]
    for frame in range(scene.frame_start, scene.frame_end + 1):
        # path coords for frame
        x0, y0, z0 = bpy.context.active_object.data.vertices[frame].co.xyz.to_tuple()
        x, y, z = bpy.context.active_object.data.vertices[frame + 1].co.xyz.to_tuple()
        z0 += anim_height
        z += anim_height

        scene.camera.position = (x0 - 5, y0 + 5, z0 + 2)
        scene.camera.look_at((x, y, z))

        scene.camera.keyframe_insert("position", frame)
        scene.camera.keyframe_insert("quaternion", frame)

        cube.position = (x, y, z)
        # cube.look_at((0, 0, 0))
        # cube.keyframe_insert("quaternion", frame)
        cube.keyframe_insert("position", frame)

        cube_light.position = (x, y, z)
        cube_light.keyframe_insert("position", frame)

    update_sky_texture()
    # --- render (and save the blender file)
    save_blend(renderer, pack=True)

# render and post-process
    log.info('starting render....')
    data_stack = renderer.render()

    subprocess.check_call('rm -rf output/pics/ || true', shell=True)
    kb.write_image_dict(data_stack, kb.as_path("output/pics/"), max_write_threads=6)

    kb.file_io.write_json(filename="output/pics/camera.json", data=kb.get_camera_info(scene.camera))
    kb.file_io.write_json(filename="output/pics/metadata.json", data=kb.get_scene_metadata(scene))
    kb.file_io.write_json(filename="output/pics/object.json", data=kb.get_instance_info(scene))
    subprocess.check_call('bash make-gifs.sh', shell=True, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)

    kb.done()


def main():
    load_addons()
    save_geometry(GEOMETRY_INPUT_FILE, GEOMETRY_SAVE_FILE)

    # EXTRA_GEOMETRY_FUNC_FILE = "/data/xxx.blend"
    # save_geometry(EXTRA_GEOMETRY_FUNC_FILE, GEOMETRY_SAVE_FILE_2)

    render_main()


if __name__ == '__main__':
    main()
