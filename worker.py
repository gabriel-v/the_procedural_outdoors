import subprocess
import logging
import pathlib
import importlib
import pprint

import kubric as kb
from kubric.renderer.blender import Blender as KubricRenderer
from kubric.core.assets import UndefinedAsset
from kubric.core.objects import FileBasedObject
import bpy

logging.basicConfig(level="INFO")
log = logging.getLogger(__name__)

MAX_FRAMES = 12
RESOLUTION_X = 333


def save_blend():
    renderer.save_state("output/trains.blend")


def pre_init_blender():
    bpy.ops.file.autopack_toggle()
    # set up
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.feature_set = 'EXPERIMENTAL'
    bpy.context.scene.view_settings.look = 'Medium High Contrast'


    # https://blender.stackexchange.com/questions/230011/why-is-area-type-none-when-starting-blender-script-from-cmd
    area_3d = [area for area in bpy.context.screen.areas if area.type == 'VIEW_3D'][0]
    space_3d = list(area_3d.spaces)[0]

    space_3d.lens = 33.3
    space_3d.clip_start = 0.01
    space_3d.clip_end = 20000


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
                            adaptive_subdivision=False, add_bbox=False,
                            bbox_scale_z=None, bbox_scale_xy=1, get_geo_extents=False):
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
    scene += cube

    bpy.data.objects[new_name].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[new_name]

    if get_geo_extents:
        _get_geo_extents()

    if convert_to_mesh:
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

    if add_bbox:
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
        bpy.ops.object.mode_set(mode='EDIT')      # switch to mesh edit mode
        bpy.ops.mesh.select_all(action='SELECT')  # select all faces
        bpy.ops.mesh.quads_convert_to_tris()      # triangulate
        bpy.ops.object.mode_set(mode='OBJECT')    # back to object mode

    if adaptive_subdivision:
        bpy.ops.object.modifier_add(type='SUBSURF')

        bpy.context.object.cycles.use_adaptive_subdivision = True
        bpy.context.object.cycles.dicing_rate = 0.9
        bpy.context.object.modifiers["Subdivision"].levels = 0

    bpy.data.objects[new_name].select_set(False)
    bpy.ops.file.pack_all()

    return cube


def make_terrain(scene):
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
            # bbox_scale_z=2, bbox_scale_xy=0.5,
            # get_geo_extents=True,
            # triangulate=True,
            adaptive_subdivision=True,
        )

    keys = sorted(sat.keys())
    for i in range(len(keys) - 1):
        big_obj = sat[keys[i]].name
        small_obj = sat[keys[i+1]].name + '__bbox'
        cut_object(big_obj, small_obj, hole_tolerant=i==0)

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

    for key in sat:
        obj = bpy.data.objects[sat[key].name]
        mat = obj.active_material
        tree = bpy.data.materials[mat.name].node_tree

        # add bump node color -> height -> normals
        bump = tree.nodes.new(type="ShaderNodeBump")
        bump.location = -200, -333
        bump.inputs.get('Strength').default_value = 0.36
        bump.inputs.get('Distance').default_value = 1.5
        tree.links.new(tree.nodes["Image Texture"].outputs.get("Color"),
                       bump.inputs.get('Height'))
        tree.links.new(bump.outputs.get('Normal'),
                       tree.nodes['Principled BSDF'].inputs.get('Normal'))

        # lower specular --> 0.1 (no shiny mountains pls)
        tree.nodes["Principled BSDF"].inputs.get('Specular').default_value = 0.1

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


    # extra stuff: paths
    import_object_from_file(
        scene,
        'path_train__1',
        pathlib.Path(f"/data/predeal1/google/tren/22/google-22-tren.blend"),
        '300',
    )
    import_object_from_file(
        scene,
        'path_train__2',
        pathlib.Path(f"/data/predeal1/google/tren/22/google-22-tren.blend"),
        '300.001',
    )

    import_object_from_file(
        scene,
        'path_car__1',
        pathlib.Path(f"/data/predeal1/google/tren/22/google-22-tren.blend"),
        'Bulevardul Mihail Săulescu',
    )
    return sat


def load_addons():
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


CUBE_BG = "cube/background.blend"

# --- create scene and attach a renderer to it
scene = kb.Scene(resolution=(RESOLUTION_X, RESOLUTION_X), frame_start=1, frame_end=MAX_FRAMES)
renderer = KubricRenderer(scene, custom_scene=CUBE_BG, custom_scene_shading=True,
                          adaptive_sampling=True, samples_per_pixel=16)
pre_init_blender()
save_blend()
load_addons()


# #### OBJECTS #####
# ============
make_terrain(scene)

# pos = .object.matrix_world.to_translation()
CUBE_FG = pathlib.Path("cube/cube.blend")
cube = import_object_from_file(scene, "Cube0", CUBE_FG, "Cube")
cube.position = (0, 0, 1100)

cube_light = kb.PointLight(name="cube_light", position=(0,0,1100), intensity=6666)
scene += cube_light

# ### CAMERA ####
# ============
camera = kb.PerspectiveCamera(name="camera", position=(6, -5, 1102),
                              look_at=(0, 0, 1100))
scene += camera
# import pdb; pdb.set_trace()
camera_obj = bpy.data.objects[camera.name]
camera_obj.data.lens = 33.3
camera_obj.data.clip_start = 0.01
camera_obj.data.clip_end = 20000

# --- populate the scene with objects, lights, cameras
# scene += kb.Cube(name="floor", scale=(10, 10, 0.1), position=(0, 0, -0.1))
# scene += kb.Sphere(name="ball", scale=1, position=(0, 0, 1.))
# scene += kb.DirectionalLight(name="sun", position=(-1, -0.5, 3),
#                              look_at=(0, 0, 0), intensity=1.5)

animation_path = 'path_car__1'
anim_height = 6
bpy.data.objects[animation_path].select_set(True)
bpy.context.view_layer.objects.active = bpy.data.objects[animation_path]
for frame in range(scene.frame_start, scene.frame_end + 1):
    i = (frame - scene.frame_start)
    # path coords for frame
    x0, y0, z0 = bpy.context.active_object.data.vertices[frame].co.xyz.to_tuple()
    x, y, z = bpy.context.active_object.data.vertices[frame+1].co.xyz.to_tuple()
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



# set sky texture altitude to height of camera
bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].altitude = camera.position[2]
# --- render (and save the blender file)
save_blend()

# render and post-process
data_stack = renderer.render()

subprocess.check_call(f'rm -rf output/pics/ || true', shell=True)
kb.write_image_dict(data_stack, kb.as_path("output/pics/"), max_write_threads=6)

kb.file_io.write_json(filename="output/pics/camera.json", data=kb.get_camera_info(scene.camera))
kb.file_io.write_json(filename="output/pics/metadata.json", data=kb.get_scene_metadata(scene))
kb.file_io.write_json(filename="output/pics/object.json", data=kb.get_instance_info(scene))
subprocess.check_call('bash make-gifs.sh', shell=True)

kb.done()
