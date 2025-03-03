# SPDX-FileCopyrightText: 2024 Jean Basset <jean.basset@inria.fr>

# SPDX-License-Identifier: CECILL-2.1

import bpy
import bmesh
import os
import numpy as np
import math
from mathutils import Vector, Matrix, Euler

def add_mesh_to_scene(name,verts=None,edges=None,faces=None,override=True):
	if override and name in bpy.data.objects:
		bpy.data.objects.remove(bpy.context.scene.objects[name], do_unlink=True)

	mesh = bpy.data.meshes.new(name)
	obj = bpy.data.objects.new(mesh.name, mesh)
	if override:
		obj.name = name

	if not "Collection" in bpy.data.collections:
		newcol = bpy.data.collections.new("Collection")
		bpy.context.scene.collection.children.link(newcol)
		
	col = bpy.data.collections["Collection"]
	col.objects.link(obj)
	# bpy.context.view_layer.objects.active = obj

	# if verts != None and faces != None:
	mesh.from_pydata(verts, edges, faces)

	return obj

def copy_obj(obj,name=None,override=True,clear_matrix_world=True):
	if override and name in bpy.context.scene.objects:
		bpy.context.scene.objects.remove(bpy.context.scene.objects[name], do_unlink=True)

	new_obj = obj.copy()
	new_obj.data = obj.data.copy()
	new_obj.animation_data_clear()
	if clear_matrix_world:
		new_obj.matrix_world = Matrix([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,0]])
	if name != None:
		new_obj.name = name
	
	bpy.context.collection.objects.link(new_obj)

	return new_obj

def delete_object(obj):
	bpy.ops.object.select_all(action='DESELECT')
	bpy.context.scene.objects[obj.name].select_set(True)
	bpy.ops.object.delete() 

def get_vertex_normals(vertices,faces):
	mesh = bpy.data.meshes.new("mesh")
	mesh.from_pydata(vertices,[],faces)
	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.verts.ensure_lookup_table()
	bm.normal_update()
	return [bm.verts[i].normal for i in range(len(bm.verts))]

def get_default_weights(n,w=1):
	return Vector([w for i in range(n)])

def get_center_of_mass(vertices,weights=[]):
	if len(weights) == 0:
		weights = get_default_weights(len(vertices))

	cm = Vector([0,0,0])
	for i in range(len(vertices)):
		cm += Vector(vertices[i])*weights[i]

	return cm/len(vertices)

def distance_object_to_object(v1,v2):
	distances = [np.linalg.norm(v1[i]-v2[j]) for i in range(len(v1)) for j in range(len(v2))]
	return min(distances),max(distances)

def distance_to_object(v,vertices):
	return min([np.linalg.norm(v-vertices[i]) for i in range(len(vertices))])

def map_intervals(x,a,b,c,d):
	# https://math.stackexchange.com/questions/914823/shift-numbers-into-a-different-range
	return c + ((d-c)/(b-a))*(x-a)

def get_anim_vertices(obj,frame_start=None,frame_end=None,camera_coord=False):
	if frame_start == None or frame_end == None:
		keyframe_frames = get_keyframe_frames(obj)
		frame_start = keyframe_frames[0]
		frame_end = keyframe_frames[-1]

	depsgraph = bpy.context.evaluated_depsgraph_get()

	anim_vertices = {}
	wm = bpy.context.window_manager
	wm.progress_begin(0,frame_end-frame_start)
	for frame in range(frame_start,frame_end+1):
		bpy.context.scene.frame_set(frame)
		wm.progress_update(frame)
		# bm = bmesh.new()
		# bm.from_object( obj, depgraph )
		# bm.verts.ensure_lookup_table()

		# anim_vertices[frame] = [obj.matrix_world @ v.co for v in bm.verts]

		ob_eval = obj.evaluated_get(depsgraph)
		anim_vertices[frame] = np.array([obj.matrix_world @ v.co for v in ob_eval.data.vertices])

		if camera_coord:
			camera = bpy.context.scene.camera
			for i in range(len(anim_vertices[frame])):
				anim_vertices[frame][i] -= camera.location
				position_vector = Vector(anim_vertices[frame][i])
				position_vector.rotate(camera.rotation_euler)
				position_vector[2] *= -1
				anim_vertices[frame][i] = np.array(position_vector)

	wm.progress_end()
	return anim_vertices

def get_anim_joints(obj,frame_start,frame_end,camera_coord=False):
	if frame_start == None or frame_end == None:
		keyframe_frames = get_keyframe_frames(obj)
		frame_start = keyframe_frames[0]
		frame_end = keyframe_frames[-1]

	anim_joints = {}
	for frame in range(frame_start,frame_end+1):
		bpy.context.scene.frame_set(frame)

		anim_joints[frame] = {}
		for mod in obj.modifiers:
			if mod.type == "ARMATURE":
				for o in bpy.context.scene.objects:
					o.select_set(False)
				bpy.context.scene.objects[mod.name].select_set(True)

				armature = bpy.context.scene.objects[mod.name]
				for b in armature.data.bones:
					bone_name = b.name
					bone = bpy.context.scene.objects[mod.name].pose.bones[bone_name]
					anim_joints[frame][bone_name] = [np.array(bpy.context.scene.objects[mod.name].matrix_world @ bone.head), np.array(bpy.context.scene.objects[mod.name].matrix_world @ bone.tail)]

	return anim_joints

def get_anim_vertices_and_joints(obj,frame_start,frame_end,bones_to_discard,camera_coord=False):
	if frame_start == None or frame_end == None:
		keyframe_frames = get_keyframe_frames(obj)
		frame_start = keyframe_frames[0]
		frame_end = keyframe_frames[-1]

	obj_copy = obj.copy()
	mods_to_remove = []
	for mod in obj_copy.modifiers:
		if mod.type == "SUBSURF":
			mods_to_remove.append(mod.name)
	for mod_name in mods_to_remove:
		obj_copy.modifiers.remove(obj_copy.modifiers[mod_name])
	
	col = obj.users_collection[0]
	col.objects.link(obj_copy)

	depsgraph = bpy.context.evaluated_depsgraph_get()

	anim_vertices = {}
	anim_joints = {}
	wm = bpy.context.window_manager
	wm.progress_begin(0,frame_end-frame_start)
	for frame in range(frame_start,frame_end+1):
		bpy.context.scene.frame_set(frame)
		wm.progress_update(frame)

		# https://blender.stackexchange.com/questions/264568/what-is-the-fastest-way-to-set-global-vertices-coordinates-to-a-numpy-array-usin
		ob_eval = obj_copy.evaluated_get(depsgraph)

		n_vertices = len(ob_eval.data.vertices)
		rotation_and_scale = obj.matrix_world.to_3x3().transposed()
		offset = np.array(obj.matrix_world.translation)
		verts_temp = np.empty(n_vertices*3,dtype=np.float64)
		ob_eval.data.vertices.foreach_get('co',verts_temp)
		verts_temp.shape = (n_vertices,3)
		verts_temp = np.matmul(verts_temp, rotation_and_scale)
		verts_temp += offset
		anim_vertices[frame] = verts_temp

		if camera_coord:
			camera = bpy.context.scene.camera
			for i in range(len(anim_vertices[frame])):
				anim_vertices[frame][i] -= camera.location
				position_vector = Vector(anim_vertices[frame][i])
				position_vector.rotate(camera.rotation_euler)
				position_vector[2] *= -1
				anim_vertices[frame][i] = np.array(position_vector)

		anim_joints[frame] = {}
		for mod in obj.modifiers:
			if mod.type == "ARMATURE":
				for o in bpy.context.scene.objects:
					o.select_set(False)
				mod.object.select_set(True)

				armature = mod.object
				M = armature.matrix_world
				p = armature.pose
				for b in armature.data.bones:
					bone_name = b.name
					if bone_name in bones_to_discard:
						bone_name = get_closest_kept_parent(b,bones_to_discard).name
					bone = p.bones[bone_name]
					anim_joints[frame][b.name] = [np.array(M @ bone.head), np.array(M @ bone.tail), bone]

	wm.progress_end()

	objs = bpy.data.objects
	objs.remove(objs[obj_copy.name],do_unlink=True)

	return anim_vertices, anim_joints

def get_closest_kept_parent(bone,bones_to_discard):
	parent = bone.parent
	if not parent.name in bones_to_discard:
		return parent
	return get_closest_kept_parent(parent, bones_to_discard)

def get_keyframe_frames(obj):
	keyframe_frames = []
	if obj.type in ['MESH','ARMATURE','CAMERA']:
		if obj.animation_data and obj.animation_data.action:
			for fc in obj.animation_data.action.fcurves :
				if fc.data_path.endswith(('location','rotation_euler','rotation_quaternion','scale')):
					for key in fc.keyframe_points :
						keyframe_frames.append(int(key.co[0]))

		if obj.data.animation_data and obj.data.animation_data.action:
			for fc in obj.data.animation_data.action.fcurves :
				if fc.data_path.endswith(('location','rotation_euler','rotation_quaternion','scale','co')):
					for key in fc.keyframe_points :
						keyframe_frames.append(int(key.co[0]))

	for mod in obj.modifiers:
		if mod.type == "ARMATURE":
			keyframe_frames += get_keyframe_frames(mod.object)

	return sorted(list(set(keyframe_frames)))

def warp(x,b):
	return ((2*(x+1))/(-math.exp(-b)*(x-1)+x+1))-1

def warp_deltas(deltas,b):
	return np.array([warp(deltas[i],b) for i in range(len(deltas))])

def curve_from_points(coords):
	curveData = bpy.data.curves.new('MyCurve', type='CURVE')
	curveData.dimensions = '3D'
	curveData.resolution_u = 20

	polyline = curveData.splines.new('BEZIER')
	polyline.bezier_points.add(len(coords)-1)
	for i, coord in enumerate(coords):
		x,y,z = coord
		# polyline.points[i].co = (x, y, z, 1)
		polyline.bezier_points[i].co = (x,y,z)
		# polyline.bezier_points[i].handle_left = (x, y, z)
		# polyline.bezier_points[i].handle_right = (x, y, z)

		polyline.bezier_points[i].handle_right_type = 'AUTO'
		polyline.bezier_points[i].handle_left_type = 'AUTO'

	# create Object
	curveOB = bpy.context.scene.objects.new('myCurve', curveData)

	# attach to scene and validate context
	col = bpy.data.collections["Collection"]
	col.objects.link(curveOB)

def get_velocities(obj,frame_start=None,frame_end=None):
	if frame_start == None or frame_end == None:
		keyframe_frames = get_keyframe_frames(obj)
		frame_start = keyframe_frames[0]
		frame_end = keyframe_frames[-1]

	original_anim_vertices = get_anim_vertices(obj,frame_start,frame_end)

	velocities = {}
	for frame in range(frame_start,frame_end+1):
		# velocities[frame] = original_anim_vertices[frame+1] - original_anim_vertices[frame]
		if frame != frame_end:
			velocities[frame] = original_anim_vertices[frame+1] - original_anim_vertices[frame]
		else:
			velocities[frame] = original_anim_vertices[frame] - original_anim_vertices[frame]

	return velocities

def smooth_step(x):
	if x <= 0:
		return 0
	if x >= 1:
		return 1
	return 3*x**2 - 2*x**3

def smooth_step_array(x):
	x = np.clip(x,0,1)
	return 3*x**2 - 2*x**3

def dist(v1,v2):
	return ((v1[0]-v2[0])**2+(v1[1]-v2[1])**2+(v1[2]-v2[2])**2)**0.5

def norm(v):
	return (v[0]**2 + v[1]**2 + v[2]**2)**0.5

def dot(v1,v2):
	return v1[0]*v2[0]+v1[1]*v2[1]+v1[2]*v2[2]