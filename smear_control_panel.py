# SPDX-FileCopyrightText: 2024 Jean Basset <jean.basset@inria.fr>

# SPDX-License-Identifier: CECILL-2.1

import bpy
import os
import cProfile
import time
from mathutils import Vector
from cProfile import Profile
from pstats import SortKey, Stats

from bpy.utils import resource_path
from pathlib import Path

from . import deltas_generation_functions as deltagen
from .utils import *

def get_bone_names(self, context, edit_text):
    bone_names = []
    if context.active_object.type == "MESH":
        for mod in context.active_object.modifiers:
            if mod.type == "ARMATURE":
                for bone in mod.object.data.bones:
                    bone_names.append(bone.name)
    return bone_names

class Panel:
    bl_idname = 'VIEW3D_PT_smear_control'
    bl_label = 'Smear frame generation'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  

class SmearControlPanel(Panel,bpy.types.Panel):
    bl_idname = "VIEW3D_PT_SmearControlPanel"
    bl_label = "Smear frame generation"
    bl_category = "SMEAR"

    def draw(self,context):
        scene = context.scene

        col = self.layout.column()

        obj = context.active_object
        isMesh = (not obj is None) and obj.type == "MESH"
        col.enabled = isMesh

        msg = f"Selected: {obj.name}" if isMesh else "Select an animated mesh"
        col.label(text=msg)

        fullBodyCheckbox = col.row()
        fullBodyCheckbox.enabled = False

        if isMesh:
            for mod in obj.modifiers:
                if mod.type == "ARMATURE":
                    fullBodyCheckbox.enabled = True
        fullBodyCheckbox.prop(scene.smear, "fullBody")

        col.label(text="Prune Skeleton")
        col.label(text="Enter bones separated by \",\".")
        col.prop(scene.smear,"discardedBone")
        col.label(text="All child bones in the hierarchy")
        col.label(text="will be discarded for baking")

        col.label(text="Temporal smoothing window:")
        col.prop(scene.smear,"smoothWindow")

        if bpy.context.scene.camera != None:
            col.prop(scene.smear,"cameraPOV")

        col.operator(BakeDeltasTrajectoriesOperator.bl_idname)

class EffectControlPanel(Panel,bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SMEAR"

    def draw(self, context):
        scene = context.scene
        col = self.layout.column()

        obj = context.active_object
        isMesh = (not obj is None) and obj.type == "MESH"
        if isMesh and "Smear Control Panel" in obj.modifiers:
            mod = obj.modifiers["Smear Control Panel"]

            param = mod.node_group.interface.items_tree[self.activate_toggle.name]
            property_name = f"[\"{param.identifier}\"]"
            col.prop(data=mod, property=property_name, text=self.activate_toggle.name)

            if mod[param.identifier]:
                for gn_param in self.effect_parameters:
                    param = mod.node_group.interface.items_tree[gn_param.name]
                    property_name = f"[\"{param.identifier}" + ("_attribute_name" if gn_param.as_attribute else "") + "\"]"
                    col.prop(data=mod, property=property_name, text=param.name)

        else:
            col.label(text="Select an animated mesh")
            col.label(text="and run Bake Smears")

class GN_parameter():
    def __init__(self, name, as_attribute=False):
        self.name = name
        self.as_attribute = as_attribute

class ElongatedInbetweensControlPanel(EffectControlPanel,bpy.types.Panel):
    bl_idname = "VIEW3D_PT_ElongatedInbetweensControlPanel"
    bl_label = "Elongated In-Betweens"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SMEAR"

    activate_toggle = GN_parameter("Activate Elongated")

    effect_parameters = [
            GN_parameter("Smear Length"),
            GN_parameter("Smear Past Length"),
            GN_parameter("Smear Future Length"),
            GN_parameter("Weight by Speed"),
            GN_parameter("Speed Factor"),
            GN_parameter("Add Noise Pattern"),
            GN_parameter("Noise Scale"),
            GN_parameter("Manual Weights"),
            GN_parameter("Manual Weights Group", as_attribute=True)
        ]

class MultipleInbetweensControlPanel(EffectControlPanel,bpy.types.Panel):
    bl_idname = "VIEW3D_PT_MultipleInbetweensControlPanel"
    bl_label = "Multiple In-Betweens"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SMEAR"

    activate_toggle = GN_parameter("Activate Multiples")

    effect_parameters = [
            GN_parameter("# Future Multiples"),
            GN_parameter("# Past Multiples"),
            GN_parameter("Future Opacity Factor"),
            GN_parameter("Past Opacity Factor"),
            GN_parameter("Future Displacement"),
            GN_parameter("Past Displacement"),
            GN_parameter("Overlap"),
            GN_parameter("Number of Overlap"),
            GN_parameter("Multiple Speed Threshold")
        ]

class MotionLinesControlPanel(EffectControlPanel,bpy.types.Panel):
    bl_idname = "VIEW3D_PT_MotionLinesControlPanel"
    bl_label = "Motion lines"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SMEAR"

    activate_toggle = GN_parameter("Activate Lines")

    effect_parameters = [
            GN_parameter("Lines Length"),
            GN_parameter("Lines Past Length"),
            GN_parameter("Lines Future Length"),
            GN_parameter("Lines Offset"),
            GN_parameter("Seed"),
            GN_parameter("Probability"),
            GN_parameter("Lines Speed threshold"),
            GN_parameter("Radius"),
            GN_parameter("Radius slope"),
            GN_parameter("Line Material")
        ]

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
        scene = context.scene
        if not self.appended_files:
            path = os.path.dirname(os.path.realpath(__file__))
            abspath = bpy.path.abspath(path)
            filepath = os.path.join(abspath, "smear_frames_nodes.blend")

            node_group_name="Smear Frames Controler"
            bpy.ops.wm.append(filepath = os.path.join(filepath, "NodeTree", node_group_name), directory = os.path.join(filepath, "NodeTree"), filename = node_group_name)
            node_group_name="Smear Frames Controler - Multiples"
            bpy.ops.wm.append(filepath = os.path.join(filepath, "NodeTree", node_group_name), directory = os.path.join(filepath, "NodeTree"), filename = node_group_name)
            node_group_name="Smear Frames Controler - Lines"
            bpy.ops.wm.append(filepath = os.path.join(filepath, "NodeTree", node_group_name), directory = os.path.join(filepath, "NodeTree"), filename = node_group_name)

            material_name="Delta_Visualization"
            bpy.ops.wm.append(filepath = os.path.join(filepath, "Material", material_name), directory = os.path.join(filepath, "Material"), filename = material_name)

            material_name="MultipleTransparency"
            bpy.ops.wm.append(filepath = os.path.join(filepath, "Material", material_name), directory = os.path.join(filepath, "Material"), filename = material_name)

            self.appended_files = True

        obj = bpy.context.active_object
        if obj.type == 'MESH':
            current_frame = bpy.context.scene.frame_current
            clear_attributes(obj)

            armature = None
            for mod in obj.modifiers:
                if mod.type == "NODES" and not (mod.node_group is None) and mod.node_group.name == "Smear Frames Controler":
                    original_identifier = mod.node_group.interface.items_tree["Original"].identifier
                    mod[original_identifier] = True
                if mod.type == "ARMATURE":
                    armature = mod.object

            frame_start = math.inf
            frame_end = 0

            keyframe_frames = get_keyframe_frames(obj)
            if len(keyframe_frames) > 0:
                frame_start = keyframe_frames[0]
                frame_end = keyframe_frames[-1]

            if bpy.context.scene.camera != None:
                keyframe_frames = get_keyframe_frames(bpy.context.scene.camera)
                if len(keyframe_frames) > 0:
                    frame_start = min(keyframe_frames[0],frame_start)
                    frame_end = max(keyframe_frames[-1], frame_end)

            bones_to_discard = []
            if armature != None and scene.smear.discardedBone != "":
                selected_bones = [armature.data.bones[bone] for bone in scene.smear.discardedBone.split(", ")]
                bones_to_discard = [child.name for b in selected_bones for child in b.children_recursive]

            positions, joints = get_anim_vertices_and_joints(obj,frame_start,frame_end,bones_to_discard,camera_coord=scene.smear.cameraPOV)

            animation_deltas = deltagen.get_animation_deltas_ribbon(obj,positions,joints,bpy.context.scene.camera,scene.smear.smoothWindow,full_body=scene.smear.fullBody)

            for frame in animation_deltas:
                dname = f"delta_{frame}"
                obj.data.attributes.new(name=dname,type="FLOAT",domain="POINT")
                obj.data.attributes[dname].data.foreach_set("value",animation_deltas[frame])


            pos_aggregated = np.concatenate([positions[frame] for frame in positions])
            add_mesh_to_scene(f"aggregated_animation_{obj.name}",verts=pos_aggregated,edges=[],faces=[])
            bpy.data.objects[f"aggregated_animation_{obj.name}"].hide_viewport = True
            bpy.data.objects[f"aggregated_animation_{obj.name}"].hide_render = True
            bpy.data.objects[f"aggregated_animation_{obj.name}"].select_set(False)
            obj.select_set(True)

            set_node_tree(obj,frame_start,frame_end,scene.smear.cameraPOV)

            bpy.context.scene.frame_set(current_frame)

        return {'FINISHED'}

def set_node_tree(obj,frame_start,frame_end,cameraPOV):
    node_tree_exists = False
    armature_exists = False
    subsurface_exists = False
    for mod in obj.modifiers:
        if mod.type == "NODES" and not (mod.node_group is None) and mod.node_group.name == "Smear Frames Controler":
            node_tree_exists = True
        if mod.type == "ARMATURE":
            armature_exists = True
        if mod.type == "SUBSURF":
            subsurface_exists = True

    if not node_tree_exists:
        mod = obj.modifiers.new("Smear Control Panel","NODES")
        smear_node_tree = bpy.data.node_groups["Smear Frames Controler"]
        mod.node_group = smear_node_tree

        # Move control panel to be the modifier just after the armature:
        if armature_exists:
            armature_index = 0
            smear_index = 0
            for i in range(len(obj.modifiers)):
                mod = obj.modifiers[i]
                if mod.type == "ARMATURE":
                    armature_index = i
                if mod.name == "Smear Control Panel":
                    smear_index = i
            
            obj.modifiers.move(smear_index,armature_index+1)
        
        # If no armature, still need to move modifier before any subdivision
        elif subsurface_exists:
            subsurface_index = 0
            smear_index = 0
            for i in range(len(obj.modifiers)):
                mod = obj.modifiers[i]
                if mod.type == "SUBSURF":
                    subsurface_index = i
                if mod.name == "Smear Control Panel":
                    smear_index = i
            
            obj.modifiers.move(smear_index,max(subsurface_index-1,0))

    mod = obj.modifiers.get("Smear Control Panel")

    object_identifier = mod.node_group.interface.items_tree["Object"].identifier
    mod[object_identifier] = obj

    aggregated_identifier = mod.node_group.interface.items_tree["Aggregated"].identifier
    mod[aggregated_identifier] = bpy.data.objects[f"aggregated_animation_{obj.name}"]

    first_frame_identifier = mod.node_group.interface.items_tree["First Frame"].identifier
    mod[first_frame_identifier] = frame_start

    last_frame_identifier = mod.node_group.interface.items_tree["Last Frame"].identifier
    mod[last_frame_identifier] = frame_end

    original_identifier = mod.node_group.interface.items_tree["Original"].identifier
    mod[original_identifier] = False

    cameraPOV_identifier = mod.node_group.interface.items_tree["Camera POV"].identifier
    mod[cameraPOV_identifier] = cameraPOV

    camera_identifier = mod.node_group.interface.items_tree["Camera"].identifier
    mod[camera_identifier] = bpy.context.scene.camera

class SmearPropertyGroup(bpy.types.PropertyGroup):
    fullBody: bpy.props.BoolProperty(name="Ignore Skeleton",default=False)
    discardedBone: bpy.props.StringProperty(name="Bones",search=get_bone_names)
    smoothWindow: bpy.props.IntProperty(name="n° frames", default=2)
    cameraPOV: bpy.props.BoolProperty(name="camera POV",default=False)

def register():
    bpy.utils.register_class(SmearPropertyGroup)
    bpy.types.Scene.smear = bpy.props.PointerProperty(type=SmearPropertyGroup)

    bpy.utils.register_class(SmearControlPanel)
    bpy.utils.register_class(BakeDeltasTrajectoriesOperator)

    bpy.utils.register_class(ElongatedInbetweensControlPanel)
    bpy.utils.register_class(MotionLinesControlPanel)
    bpy.utils.register_class(MultipleInbetweensControlPanel)

def unregister():
    bpy.utils.unregister_class(SmearPropertyGroup)
    del bpy.types.Scene.smear

    bpy.utils.unregister_class(SmearControlPanel)
    bpy.utils.unregister_class(BakeDeltasTrajectoriesOperator)

    bpy.utils.unregister_class(ElongatedInbetweensControlPanel)
    bpy.utils.unregister_class(MotionLinesControlPanel)
    bpy.utils.unregister_class(MultipleInbetweensControlPanel)