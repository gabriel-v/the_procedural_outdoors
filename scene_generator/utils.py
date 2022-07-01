import os
import importlib
import pathlib
import logging
import contextlib

import bpy
import kubric as kb

log = logging.getLogger(__name__)

from . import settings


@contextlib.contextmanager
def make_active_object(name):
    assert name in bpy.data.objects
    obj = bpy.data.objects[name]
    log.info('set active object = %s', name)
    try:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        yield obj
    finally:
        obj.select_set(False)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = None


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


def save_blend(renderer, destination=settings.MAIN_BLEND_FILE, pack=False):
    log.info('----- > SAVING %s ... < ------', destination)
    if pack:
        bpy.ops.file.pack_all()
    renderer.save_state(destination)
    log.info('----- > SAVED %s < ------', destination)


def pre_init_blender(renderer):
    """ Set up blender after kubric renderer instantiation with extra settings """
    log.info('init settings...')
    bpy.context.scene.render.engine = 'CYCLES'
    # bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    bpy.context.scene.cycles.feature_set = 'EXPERIMENTAL'
    bpy.context.scene.view_settings.look = 'Medium High Contrast'
    bpy.context.scene.cycles.use_preview_denoising = True

    # compositor use opencl & buffering & medium quality
    bpy.context.scene.render.use_persistent_data = True

    # TODO remove OpenCL to fix optical flow
    bpy.data.scenes["Scene"].node_tree.use_opencl = True
    bpy.data.scenes["Scene"].node_tree.use_groupnode_buffer = True
    bpy.data.scenes["Scene"].node_tree.render_quality = 'MEDIUM'
    bpy.data.scenes["Scene"].node_tree.edit_quality = 'MEDIUM'

    # https://blender.stackexchange.com/questions/230011/why-is-area-type-none-when-starting-blender-script-from-cmd
    for area_3d in [area for area in bpy.context.screen.areas if area.type == 'VIEW_3D']:
        for space_3d in area_3d.spaces:
            space_3d.lens = settings.CAMERA_LENS
            space_3d.clip_start = settings.CAMERA_CLIP_START
            space_3d.clip_end = settings.CAMERA_CLIP_END

    if os.getenv("KUBRIC_USE_GPU", "False").lower() in ("true", "1", "t"):
        log.info('enable gpu for main render...')
        bpy.context.preferences.addons["cycles"].preferences.get_devices()
        renderer.use_gpu = True
        bpy.context.scene.cycles.device = 'GPU'
        for scene in bpy.data.scenes:
            scene.cycles.device = 'GPU'
        # log.info('compute device values: %s',
        #       list(bpy.context.preferences
        #            .system.bl_rna.properties['compute_device'].enum_items.keys()))
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "CUDA"
        for d in bpy.context.preferences.addons["cycles"].preferences.devices:
            d["use"] = 1  # Using all devices, include GPU and CPU
            print(d["name"], d["use"])

        devices_used = [d.name for d in bpy.context.preferences.addons["cycles"].preferences.devices
                        if d.use]
        log.warning("\n =========== GPU\n =========>>> Using the following GPU Device(s): %s",
                    devices_used)

    # bpy.context.scene.render.threads_mode = 'FIXED'
    bpy.context.scene.render.threads = settings.RENDER_THREAD_COUNT
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
    bpy.context.scene.cycles.time_limit = settings.RENDER_TIME_LIMIT
    bpy.context.scene.cycles.samples = settings.SAMPLES_PER_PIXEL
    bpy.context.scene.cycles.preview_samples = settings.SAMPLES_PER_PIXEL


def cut_object(target_id, cutout_id, exact=False, hole_tolerant=True,
               solidify=False, op='DIFFERENCE', apply=True):
    log.info('cutting %s out of %s', cutout_id, target_id)

    # bpy.context.view_layer.objects.active = bpy.data.objects[target_id]
    with make_active_object(target_id) as obj:

        bpy.ops.object.modifier_add(type='BOOLEAN')
        bpy.context.object.modifiers["Boolean"].operation = op
        bpy.context.object.modifiers["Boolean"].object = bpy.data.objects[cutout_id]

        if exact:
            bpy.context.object.modifiers["Boolean"].solver = 'EXACT'
            bpy.context.object.modifiers["Boolean"].use_self = False
            bpy.context.object.modifiers["Boolean"].use_hole_tolerant = hole_tolerant
        else:
            bpy.context.object.modifiers["Boolean"].solver = 'FAST'
            bpy.context.object.modifiers["Boolean"].double_threshold = 0

        if apply:
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
    assert pathlib.Path(orig_filename).is_file(), 'file not found'
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
    assert cube is not None, 'object not found'
    if not exclude_from_scene:
        scene += cube

    bpy.data.objects[new_name].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[new_name]

    # if get_geo_extents:
    #     _get_geo_extents()

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
    mod.angle_limit = 0.0174533
    mod.use_dissolve_boundaries = False
    return mod


def _triangulate_modifier(obj):
    modifier_name = 'triangulate_beauty'
    mod = obj.modifiers.new(modifier_name, 'TRIANGULATE')
    # mod.keep_custom_normals = True
    mod.ngon_method = 'BEAUTY'
    mod.quad_method = 'BEAUTY'
    return mod


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


def enable_adaptive_subdivision(object_list):
    log.info('enabling adaptive subdivision for %s objects', len(object_list))
    for obj in object_list:
        with make_active_object(obj.name):
            bpy.ops.object.modifier_add(type='SUBSURF')
            bpy.context.object.cycles.use_adaptive_subdivision = True
            bpy.context.object.cycles.dicing_rate = 0.9
            bpy.context.object.modifiers["Subdivision"].levels = 0


def load_addons():
    log.info('loading addons')
    # bpy.ops.preferences.addon_install(filepath='/addons/BlenderGIS/__init__.py')
    bpy.ops.preferences.addon_enable(module='BlenderGIS')

    print(bpy.context.preferences.addons['BlenderGIS'].preferences.demServerJson)
    # api_key = 'xxxxx'
    # if 'API_Key' not in bpy.context.preferences.addons['BlenderGIS'].preferences.demServer:
    # bpy.context.preferences.addons['BlenderGIS'].preferences.demServer += f"&API_Key={api_key}"
    bpy.ops.wm.save_userpref()
