import random
import logging
import pathlib

log = logging.getLogger(__name__)

import bpy

from .geometry import new_geometry_modifier
from .geometry import import_geometry_cube
from .utils import blend_append_object
from .utils import make_active_object
from .utils import make_active_collection
from .utils import import_object_from_file
from .utils import cut_object
from .utils import _decimate_dissolve
from .utils import _triangulate_modifier
from . import settings


def load_random_trees_highpoly(tree_count=30):
    log.info('importing %s x hi poly trees', tree_count)
    with open('cube/tree-assets.txt', 'r') as f:
        tree_blend_files = [pathlib.Path(x.strip()) for x in f.readlines()]

    tree_blend_files = random.sample(tree_blend_files, tree_count)

    with make_active_collection('trees_high_poly') as c:
        for blend_path in tree_blend_files:
            tree_id = blend_path.stem.split('-')[0][6:]
            tree = blend_append_object(blend_path, tree_id, active_collection=True)
            # tree.hide_render = True
            # tree.hide_viewport = True

    return c


def load_buildings(scene, sat, apply_mod=False):
    log.info('loading buildings...')
    # import buiildings last, so the shrinkwrap works over the extra-bent terrain
    import_object_from_file(
        scene,
        'buildings',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Areas:building',
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )
    with make_active_object('buildings') as obj:
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

        if apply_mod:
            bpy.ops.object.modifier_apply(modifier=g1.name)
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

        with make_active_object(sat[key].name) as obj:
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

    # set up sat shader
    for key in sat:
        with make_active_object(sat[key].name) as obj:
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


PATHS_INIT_SUBSURF_LEVELS = 4


def import_paths(scene, sat):
    log.info('importing paths...')

    import_object_from_file(
        scene,
        'roads',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Ways:highway',
        convert_to_curve=True,
        subsurf_levels=PATHS_INIT_SUBSURF_LEVELS,
        # shrinkwrap_to_plane='sat_18',
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )

    import_object_from_file(
        scene,
        'rails',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Ways:railway',
        subsurf_levels=PATHS_INIT_SUBSURF_LEVELS,
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
        "bushes": [
            "Bush-01",
            "Bush-02",
            "Bush-03",
            "Bush-04",
            "Bush-05",
        ],
        "weeds": [
            "Clover-01",
            "Clover-02",
            "Clover-03",
            "Clover-04",
            "Clover-05",
            "Grass-01",
            "Grass-02",
            "Grass-03",
            "Flowers-01",
            "Flowers-02",
            "Flowers-03",
            "Flowers-04",
        ],
    }
    with make_active_collection(veg_type + '_low_poly') as c:
        for obj_name in LOWPOLY_OBJECT_NAMES[veg_type]:
            tree = blend_append_object(LOWPOLY_VEG_FILE, obj_name, active_collection=True)
            # tree.hide_render = True
            # tree.hide_viewport = True

    return c


def make_trees(scene, camera_obj, sat, roads, rails, buildings, load_highpoly=False):
    log.info('making trees...')

    if load_highpoly:
        trees_collection = load_random_trees_highpoly(settings.RANDOM_TREE_COUNT)
    else:
        trees_collection = load_lowpoly_vegetation('trees')
        bushes_collection = load_lowpoly_vegetation('bushes')
        weeds_collection = load_lowpoly_vegetation('weeds')

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

        with make_active_object(obj.name):
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
                    "Input_5": sat_obj,
                    "Input_6": roads,
                    "Input_7": rails,
                    "Input_8": buildings,
                    "Input_10": bushes_collection,
                    "Input_11": weeds_collection,
                    # "Input_4_attribute_name": 'paths',
                },
            )
            # bpy.ops.object.geometry_nodes_input_attribute_toggle(
            #     prop_path="[\"Input_4_use_attribute\"]",
            #     modifier_name=g1.name,
            # )

            ret_list.append(obj)
    return ret_list


def make_terrain(scene, camera_obj, add_trees=False):
    log.info('creating terrain...')
    sat = make_sat(scene)
    keys = sorted(sat.keys())
    import_paths(scene, sat)

    # import geometry container cube
    import_geometry_cube(settings.GEOMETRY_SAVE_FILE)
    # import_geometry_cube(GEOMETRY_SAVE_FILE_2)

    geo_mods = {}
    for zoom in sat:
        # select land obj
        with make_active_object(sat[zoom].name) as sat_obj:
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

            # bpy.data.objects[sat[zoom].name].vertex_groups.new(name='paths')
            # geo_mods[zoom]["Output_2_attribute_name"] = "paths"

            # bpy.data.objects[sat[zoom].name].vertex_groups.new(name='rails_prox')
            # geo_mods[zoom]["Output_6_attribute_name"] = "rails_prox"

            # bpy.data.objects[sat[zoom].name].vertex_groups.new(name='roads_prox')
            # geo_mods[zoom]["Output_7_attribute_name"] = "roads_prox"

            # bpy.data.objects[sat[zoom].name].vertex_groups.new(name='limit_terrain_prox')
            # geo_mods[zoom]["Output_8_attribute_name"] = "limit_terrain_prox"

            # after geometry, do a decimate with a low angle to reduce redundant faces
            _decimate_dissolve(bpy.data.objects[sat[zoom].name])
            _triangulate_modifier(bpy.data.objects[sat[zoom].name])

    for outer_zoom, inner_zoom in zip(keys, keys[1:]):
        geo_mods[outer_zoom]['Input_5'] = bpy.data.objects[sat[inner_zoom].name]

    # terrain is reshaped; bring the buildings / paths

    # rails_center -- used for animating the camera
    import_object_from_file(
        scene,
        'rails_center',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Ways:railway',
        subsurf_levels=PATHS_INIT_SUBSURF_LEVELS,
        # convert_to_curve=True,
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )

    # cut_object('rails_center', sat[list(sat.keys())[-1]].name + '__bbox', op='INTERSECT', apply=False)

    # make rail tracks
    import_object_from_file(
        scene,
        'rails_tracks_object',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Ways:railway',
        subsurf_levels=PATHS_INIT_SUBSURF_LEVELS,
        # convert_to_curve=True,
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )
    new_geometry_modifier(
        'rails_tracks_object',
        'make_rail_tracks',
        'make_rail_tracks',
    )

    # make rail planks and bolts and shit
    import_object_from_file(
        scene,
        'rails_planks_object',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Ways:railway',
        subsurf_levels=PATHS_INIT_SUBSURF_LEVELS,
        # convert_to_curve=True,
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )
    new_geometry_modifier(
        'rails_planks_object',
        'make_rail_planks',
        'make_rail_planks',
        {
            'Input_2': camera_obj,
        }
    )

    # make rail electric poles & signals
    import_object_from_file(
        scene,
        'rails_electric_poles_object',
        pathlib.Path("/data/predeal1/google/tren/15-single-object/google-15-tren.blend"),
        'Ways:railway',
        subsurf_levels=PATHS_INIT_SUBSURF_LEVELS,
        # convert_to_curve=True,
        shrinkwrap_to_planes=[s.name for s in sat.values()],
    )

    # apply buildings geometry node when loading, since we want adaptive subdivision
    building_object = load_buildings(scene, sat, apply_mod=False)

    # now that we have buildings, we can finalize terrain height with buildings
    for zoom in keys:
        geo_mods[zoom]['Input_9'] = bpy.data.objects[building_object.name]

    # apply all the sat geo mods from above
    for zoom in sat:
        with make_active_object(sat[zoom].name) as sat_obj:
            for mod in sat_obj.modifiers:
                log.info(
                    'applying modifier %s on object %s',
                    mod.name.encode('ascii', 'backslashreplace').decode('ascii'),
                    sat_obj.name,
                )
                bpy.ops.object.modifier_apply(modifier=mod.name)
    geo_mods = {}

    # add geom modifiers to get prox to various things, output vertex group floats
    # roads range 5m
    # rails range 4m
    # building range 3m

    for zoom in sat:
        with make_active_object(sat[zoom].name) as sat_obj:
            sat_obj.vertex_groups.new(name='rails_prox')
            sat_obj.vertex_groups.new(name='roads_prox')
            sat_obj.vertex_groups.new(name='buildings_prox')
            sat_obj.vertex_groups.new(name="map_UV_1m")
            new_geometry_modifier(
                sat_obj.name,
                'set_proximity_vertex_groups',
                'set_proximity_vertex_groups',
                {
                    'Input_2': bpy.data.objects["rails"],
                    'Input_4': bpy.data.objects["roads"],
                    'Input_6': bpy.data.objects["buildings"],
                    "Output_3_attribute_name": 'rails_prox',
                    "Output_5_attribute_name": 'roads_prox',
                    "Output_7_attribute_name": 'buildings_prox',
                    "Output_8_attribute_name": 'map_UV_1m',
                }
            )

    if add_trees:
        make_trees(
            scene, camera_obj, sat,
            bpy.data.objects['roads'],
            bpy.data.objects['rails'],
            building_object,
        )

    # make_view_culling_geonodes(sat, camera_obj)

    # at the end, apply adaptive subdivision for all relevant objects
    # log.info('enabling adaptive subdivision...')
    # objects_for_adaptive_subdivision = \
    #     [bpy.data.objects[sat[zoom].name] for zoom in sat] + [building_object]
    # enable_adaptive_subdivision(objects_for_adaptive_subdivision)

    return sat
