# Copyright 2022 The Kubric Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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

import argparse
import logging
from kubric.safeimport.bpy import bpy

from kubric.assets.asset_preprocessing import export_collection

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender_file", type=str)
    parser.add_argument("--collection", type=str, default="Objects")
    parser.add_argument("--output_dir", type=str, default="exported_assets")
    FLAGS, unused = parser.parse_known_args()
    logging.info("Flags: %s", repr(FLAGS))
    logging.info("Clearing / resetting Blender...")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    logging.info("Opening '%s' ...", FLAGS.blender_file)
    bpy.ops.wm.open_mainfile(filepath=FLAGS.blender_file)
    logging.info("Exporting the %s collection to directory '%s'", FLAGS.collection, FLAGS.output_dir)

    # from https://github.com/google-research/kubric/issues/222
    for collection in bpy.data.collections:
        if collection.name == FLAGS.collection:
            for obj in collection.all_objects:
                name = obj.name

                bpy.data.objects[name].select_set(True)
                bpy.context.view_layer.objects.active = bpy.data.objects[name]

                bpy.ops.object.mode_set(mode='EDIT')      # switch to mesh edit mode
                bpy.ops.mesh.select_all(action='SELECT')  # select all faces
                bpy.ops.mesh.quads_convert_to_tris()      # triangulate
                bpy.ops.object.mode_set(mode='OBJECT')    # back to object mode

                bpy.data.objects[name].select_set(False)

    export_collection(FLAGS.collection, FLAGS.output_dir)
