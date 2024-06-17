# SPDX-FileCopyrightText: 2024 Jean Basset <jean.basset@inria.fr>

# SPDX-License-Identifier: CECILL-2.1

import bpy
import os
import sys
import cProfile
import time
from mathutils import Vector
from cProfile import Profile
from pstats import SortKey, Stats

from bpy.utils import resource_path
from pathlib import Path

addon = True
if addon:
    USER = Path(resource_path('USER'))
    src = USER / "scripts/addons" / "Smear"

    from . import deltas_generation_functions as deltagen
    from . import utils

    import imp
    imp.reload(deltagen)
    imp.reload(utils)

    from .utils import *

else:
    dir = os.path.dirname(bpy.data.filepath)
    if not dir in sys.path:
        sys.path.append(dir )

    import deltas_generation_functions as deltagen
    import utils

    import imp
    imp.reload(deltagen)
    imp.reload(utils)

    from utils import *

class Panel:
    bl_idname = 'VIEW3D_PT_smear_control'
    bl_label = 'Smear frame generation'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  

class SmearControlPanel(Panel,bpy.types.Panel):
    bl_idname = "SmearControlPanel"
    bl_label = "Smear frame generation"

    def draw(self,context):
        scene = context.scene

        col = self.layout.column()

        isMesh = (not context.active_object is None) and context.active_object.type == "MESH"
        col.enabled = isMesh

        msg = f"Selected: {context.active_object.name}" if isMesh else "Select an animated mesh"
        col.label(text=msg)

        fullBodyCheckbox = col.row()
        fullBodyCheckbox.enabled = False

        if isMesh:
            for mod in context.active_object.modifiers:
                if mod.type == "ARMATURE":
                    fullBodyCheckbox.enabled = True
        fullBodyCheckbox.prop(scene, "fullBody")

        col.label(text="Prune Skeleton")
        col.label(text="Select a bone. All child bones in the hierarchy will be discarded for smears baking")

        col.prop(scene,"discardedBone")

        col.label(text="Temporal smoothing window:")
        col.prop(scene,"smoothWindow")

        col.prop(scene,"cameraPOV")

        col.operator(BakeDeltasTrajectoriesOperator.bl_idname)

def clear_attributes(obj):
    attributes = obj.data.attributes
    to_remove = []
    for at in attributes:
        if at.name.startswith("upsampled") or at.name.startswith("delta") or at.name.startswith("velocities") or at.name.startswith("positions"):
            to_remove.append(at.name)

    for name in to_remove:
        obj.data.attributes.remove(obj.data.attributes[name])

class BakeDeltasTrajectoriesOperator(bpy.types.Operator):
    bl_idname = "scene.bake_deltas_and_trajectories"
    bl_label = "Bake Smears"

    appended_files = False

    def execute(self,context):
        tinit = time.time()
        if addon and not self.appended_files:
            filepath="smear_frames_nodes.blend"

            directory=str(src / "smear_frames_nodes.blend" / "NodeTree")
            filename="Smear Frames Controler"
            bpy.ops.wm.append(filepath=filepath, directory=directory, filename=filename)
            filename="Smear Frames Controler - Multiples"
            bpy.ops.wm.append(filepath=filepath, directory=directory, filename=filename)
            filename="Smear Frames Controler - Lines"
            bpy.ops.wm.append(filepath=filepath, directory=directory, filename=filename)

            directory=str(src / "smear_frames_nodes.blend" / "Material")
            filename="Delta_Visualization"
            bpy.ops.wm.append(filepath=filepath, directory=directory, filename=filename)

            self.appended_files = True

        obj = bpy.context.active_object
        if obj.type == 'MESH':
            clear_attributes(obj)

            armature = None
            scale_delta = 1.0
            for mod in obj.modifiers:
                if mod.type == "NODES" and not (mod.node_group is None) and mod.node_group.name == "Smear Frames Controler":
                     for inp in mod.node_group.inputs:
                        if inp.name == "Smear Length":
                            scale_delta = mod[inp.identifier]
                            mod[inp.identifier] = 0.0
                if mod.type == "ARMATURE":
                    armature = mod.object

            frame_start = math.inf
            frame_end = 0

            keyframe_frames = get_keyframe_frames(obj)
            if len(keyframe_frames) > 0:
                frame_start = keyframe_frames[0]
                frame_end = keyframe_frames[-1]

            keyframe_frames = get_keyframe_frames(bpy.context.scene.camera)
            if len(keyframe_frames) > 0:
                frame_start = min(keyframe_frames[0],frame_start)
                frame_end = max(keyframe_frames[-1], frame_end)

            # positions = get_anim_vertices(obj,frame_start,frame_end)
            # joints = get_anim_joints(obj,frame_start,frame_end)

            bones_to_discard = []
            if armature != None and context.scene.discardedBone != "":
                selected_bones = [armature.data.bones[context.scene.discardedBone]]
                # selected_bones = [armature.data.bones["mixamorig:RightForeArm"],armature.data.bones["mixamorig:LeftForeArm"]]
                # print(selected_bones)
                bones_to_discard = [child.name for b in selected_bones for child in b.children_recursive]
            # bones_to_discard = ["mixamorig:RightForeArm","mixamorig:LeftForeArm"]

            positions, joints = get_anim_vertices_and_joints(obj,frame_start,frame_end,bones_to_discard,camera_coord=context.scene.cameraPOV)
            # print(len(joints[1]))

            # Get deltas
            # with Profile() as profile:
            #     print(f"{get_anim_vertices_and_joints(obj,frame_start,frame_end)}")
            #     (
            #         Stats(profile)
            #         .strip_dirs()
            #         .sort_stats(SortKey.CUMULATIVE)
            #         .print_stats()
            #     )
            animation_deltas = deltagen.get_animation_deltas_ribbon(obj,positions,joints,bpy.context.scene.camera,bpy.context.scene.smoothWindow,full_body=context.scene.fullBody)

            for frame in animation_deltas:
                dname = f"delta_{frame}"
                obj.data.attributes.new(name=dname,type="FLOAT",domain="POINT")
                obj.data.attributes[dname].data.foreach_set("value",animation_deltas[frame])

            # Get deltas camera coordinates
            # animation_deltas = deltagen.get_animation_deltas_ribbon(obj,positions,joints,bpy.context.scene.camera,bpy.context.scene.smoothWindow,full_body=context.scene.fullBody,camera_coord=bpy.context.scene.cameraPOV)
            # delta_fct_id = context.scene.delta_fct
            # animation_deltas_camera = deltagen.get_animation_deltas(obj,delta_functions[delta_fct_id],camera_coord=True)
            # animation_deltas_camera = deltagen.get_animation_deltas_multiple_planes(obj,delta_functions[delta_fct_id],camera_coord=True)

            # for frame in animation_deltas_camera:
                # dname = f"delta_camera_{frame}"
                # obj.data.attributes.new(name=dname,type="FLOAT",domain="POINT")
                # obj.data.attributes[dname].data.foreach_set("value",animation_deltas_camera[frame])

            pos_aggregated = np.concatenate([positions[frame] for frame in positions])
            add_mesh_to_scene(f"aggregated_animation_{obj.name}",verts=pos_aggregated,edges=[],faces=[])
            bpy.data.objects[f"aggregated_animation_{obj.name}"].hide_viewport = True
            bpy.data.objects[f"aggregated_animation_{obj.name}"].hide_render = True
            bpy.data.objects[f"aggregated_animation_{obj.name}"].select_set(False)
            obj.select_set(True)

            # positions_camera = get_anim_vertices(obj,frame_start,frame_end,camera_coord=True)
            # pos_camera_aggregated = np.concatenate([positions_camera[frame] for frame in positions_camera])
            # add_mesh_to_scene(f"aggregated_animation_camera_{obj.name}",verts=pos_camera_aggregated,edges=[],faces=[])

            set_node_tree(obj,frame_start,frame_end,scale_delta)

        print(time.time()-tinit)
        print(frame_end-frame_start+1)
        print((time.time()-tinit)/(frame_end-frame_start+1))
        return {'FINISHED'}

def set_node_tree(obj,frame_start,frame_end,scale_delta):
    node_tree_exists = False
    for mod in obj.modifiers:
        if mod.type == "NODES" and not (mod.node_group is None) and mod.node_group.name == "Smear Frames Controler":
            node_tree_exists = True

    if not node_tree_exists:
        mod = obj.modifiers.new("Smear Control Panel","NODES")
        smear_node_tree = bpy.data.node_groups["Smear Frames Controler"]
        mod.node_group = smear_node_tree

    mod = obj.modifiers.get("Smear Control Panel")
    for inp in mod.node_group.inputs:
        if inp.name == "Object":
            mod[inp.identifier] = obj
        elif inp.name == "Aggregated":
            mod[inp.identifier] = bpy.data.objects[f"aggregated_animation_{obj.name}"]
        elif inp.name == "First Frame":
            mod[inp.identifier] = frame_start
        elif inp.name == "Last Frame":
            mod[inp.identifier] = frame_end
        elif inp.name == "Smear Length":
            mod[inp.identifier] = scale_delta

def get_bone_names(self, context, edit_text):
    bone_names = []
    if context.active_object.type == "MESH":
        for mod in context.active_object.modifiers:
            if mod.type == "ARMATURE":
                for bone in mod.object.data.bones:
                    bone_names.append(bone.name)
    return bone_names

def register():
    bpy.types.Scene.fullBody = bpy.props.BoolProperty(name="Ignore Skeleton",default=False)
    bpy.types.Scene.discardedBone = bpy.props.StringProperty(name="Bone",search=get_bone_names)
    bpy.types.Scene.smoothWindow = bpy.props.IntProperty(name="n° frames", default=2)
    bpy.types.Scene.cameraPOV = bpy.props.BoolProperty(name="camera POV",default=False)

    bpy.utils.register_class(SmearControlPanel)
    bpy.utils.register_class(BakeDeltasTrajectoriesOperator)

def unregister():
    bpy.utils.unregister_class(SmearControlPanel)
    bpy.utils.unregister_class(BakeDeltasTrajectoriesOperator)

if __name__ == "__main__":
    register()
    print("Execution ended")