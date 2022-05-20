import sys
import shutil
import os
from multiprocessing import Pool
import logging
import pathlib

import kubric as kb
from kubric.redirect_io import RedirectStream
from kubric.renderer.blender import Blender as KubricRenderer

import bpy

from worker import pre_init_blender, save_blend

logging.basicConfig(level="INFO")
log = logging.getLogger(__name__)

RESOLUTION_X = 666

BG = "cube/background.blend"

TREE_IMPORT_DIR = "/data/trees/MT_PM_V60/MT_PM_V60_Blender_CyclesEevee"
TREE_OUTPUT_DIR = 'output/trees'

LEVEL_COUNT = 11


def get_objects():
    """Returns list of (path, obj_name) to import."""
    for p in pathlib.Path(TREE_IMPORT_DIR).glob('*.blend'):
        yield (p, p.stem)


def import_object(blend_path, object_name):
    blend_path = pathlib.Path(blend_path)
    section = "Object"
    log.info("Importing Geometry Nodes from file: %s/%s ...", blend_path.name, object_name)
    filepath = str(blend_path / section / object_name)
    directory = str(blend_path / section) + '/'

    # log.info("bpy.ops.wm.append( filepath='%s', filename='%s', directory='%s')",
    #          filepath, object_name, directory)
    ap_rv = bpy.ops.wm.append(
        filepath=filepath,
        filename=object_name,
        directory=directory,
        set_fake=False,
        use_recursive=False,
        do_reuse_local_id=False,
        active_collection=False,
    )

    cube = bpy.data.objects[object_name]
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube
    return cube


def _prepare_blender_render_settings():
    bpy.context.scene.render.use_compositing = False
    bpy.context.scene.render.use_sequencer = False
    bpy.context.scene.render.use_stamp_note = True
    bpy.context.scene.render.stamp_note_text = "aaaaaa"
    bpy.context.scene.render.use_stamp = True
    bpy.context.scene.render.use_stamp_filename = False
    bpy.context.scene.render.use_stamp_scene = False
    bpy.context.scene.render.use_stamp_camera = False
    bpy.context.scene.render.use_stamp_frame = False
    bpy.context.scene.render.use_stamp_memory = True
    bpy.context.scene.render.use_stamp_filename = True


def decimate_collapse(ratio=0.7):
    log.info('decimate_collapse(ratio=%s)', ratio)
    bpy.ops.object.modifier_add(type='DECIMATE')
    bpy.context.object.modifiers["Decimate"].decimate_type = 'COLLAPSE'
    bpy.context.object.modifiers["Decimate"].ratio = ratio
    bpy.ops.object.modifier_apply(modifier="Decimate")


def decimate_dissolve(angle_limit=0.2):
    log.info('decimate_dissolve(angle_limit=%s)', angle_limit)
    bpy.ops.object.modifier_add(type='DECIMATE')
    bpy.context.object.modifiers["Decimate"].decimate_type = 'DISSOLVE'
    bpy.context.object.modifiers["Decimate"].angle_limit = angle_limit
    # bpy.context.object.modifiers["Decimate"].use_dissolve_boundaries = True
    bpy.ops.object.modifier_apply(modifier="Decimate")


def dissolve_degenerate(threshold):
    log.info('dissolve_degenerate(threshold=%s)', threshold)
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.dissolve_degenerate(threshold=threshold)
    bpy.ops.object.editmode_toggle()


def remove_doubles(threshold):
    log.info('remove_doubles(threshold=%s)', threshold)
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=threshold,
                                use_unselected=True, use_sharp_edge_from_normals=True)
    bpy.ops.object.editmode_toggle()


def uglify_model(obj, level, dims, effect={}):
    avg_dim = sum(dims) / len(dims)
    log.info('uglify(level=%s, avg_dims=%s)', level, avg_dim)

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # low level = low banging up
    LEVEL_SCALE = 8
    effect_scale = (level / LEVEL_SCALE)**1.5
    if effect_scale > 2:
        effect_scale = 2

    MULTIPLIER = 0.22

    if not effect or effect.get('a'):
        decimate_dissolve(MULTIPLIER * effect_scale)
    if not effect or effect.get('b'):
        decimate_collapse(1 - effect_scale * MULTIPLIER)
    if not effect or effect.get('c'):
        remove_doubles(avg_dim * effect_scale * MULTIPLIER)
    if not effect or effect.get('d'):
        dissolve_degenerate(avg_dim * effect_scale * MULTIPLIER)


def _make_lowpoly(path, name, effect=dict()):
    scene = kb.Scene(resolution=(RESOLUTION_X, RESOLUTION_X))
    renderer = KubricRenderer(scene, custom_scene=BG, custom_scene_shading=True,
                              samples_per_pixel=8,)
    pre_init_blender()

    obj = import_object(path, name)
    dims = obj.dimensions.to_tuple()
    dim_x, dim_y, dim_z = dims
    log.info('import done for %s ----> size=%s', name, dims)

    CAM_DIST = 1.5
    cam_x = dim_x * CAM_DIST
    cam_y = dim_y * CAM_DIST
    cam_z = dim_z / 3
    camera = kb.PerspectiveCamera(name="camera", position=(cam_x, cam_y, cam_z),
                                  look_at=(0, 0, dim_z / 2))
    scene += camera

    pre_init_blender()
    _prepare_blender_render_settings()

    out_dir = os.path.join(TREE_OUTPUT_DIR, name)
    if effect:
        out_dir += '__' + '_'.join(effect.keys())
    os.makedirs(out_dir)
    for level in range(1, LEVEL_COUNT + 1):
        log.info('======\n level %s', level)
        out_blend = os.path.join(out_dir, f'blend_{name}-{level}.blend')
        out_png = os.path.join(out_dir, f'pic_{name}-{level}.png')
        out_png_2 = os.path.join(TREE_OUTPUT_DIR, f'{name}__{level}.png')
        if level > 0:
            log.info('starting processing...')
            uglify_model(obj, level, dims, effect)
            log.info('processing done.')

        if level in [3, 7, 11]:
            save_blend(renderer, out_blend, pack=True)

        _prepare_blender_render_settings()

        with RedirectStream(stream=sys.stdout):
            bpy.context.scene.render.filepath = out_png
            bpy.ops.render.render(animation=False, write_still=True)
        log.info("Rendered frame '%s'", bpy.context.scene.render.filepath)
        if not effect:
            shutil.copy(out_png, out_png_2)

    # log.info('rendering frame...')
    # frame = renderer.render_still(return_layers=('rgba',))
    # kb.write_png(frame["rgba"], out_png)
    # log.info('frame rendered')


def make_lowpoly(blendfile, objname, effect=dict()):
    # log.info('========\nimporting %s from %s', objname, blendfile)
    # p = Process(target=_make_lowpoly, args=(blendfile, objname, effect))
    # p.start()
    # p.join()
    try:
        _make_lowpoly(blendfile, objname, effect)
    except Exception as e:
        log.error('error: %s', str(e))


def main(delete=False):
    if delete:
        try:
            shutil.rmtree(TREE_OUTPUT_DIR)
        except BaseException:
            pass

    items = sorted(list(get_objects()))
    item_count = len(items)
    log.info('importing %s trees!', item_count)
    args = []
    for path, name in items:
        # args.append((path, name, {'a': True}))
        # args.append((path, name, {'b': True}))
        # args.append((path, name, {'c': True}))
        # args.append((path, name, {'d': True}))
        args.append((path, name, dict()))

    with Pool(6) as p:
        p.starmap(make_lowpoly, args)


if __name__ == '__main__':
    main()
