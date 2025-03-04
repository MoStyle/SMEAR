# SPDX-FileCopyrightText: 2024 Jean Basset <jean.basset@inria.fr>

# SPDX-License-Identifier: CECILL-2.1

import numpy as np
import bpy
import time

from cProfile import Profile
from pstats import SortKey, Stats

from .utils import *

def temporal_smooth_delta(animation_deltas,n_samples,frame_start,frame_end,n_vertices):
	w = lambda x: (1-x**2)**2
	weights = [w(f/(n_samples+1)) for f in range(-n_samples,n_samples+1)]
	animation_deltas_smoothed = {}
	for frame in range(frame_start,frame_end+1):
		sampled_frames = range(frame-n_samples,frame+n_samples+1)
		sampled_frames_clamped = [max(frame_start,min(frame_end,f)) for f in sampled_frames]

		animation_deltas_smoothed[frame] = np.sum(np.transpose(np.transpose([animation_deltas[f] for f in sampled_frames_clamped]) * weights),axis=0)/sum(weights)

	return animation_deltas_smoothed

def get_animation_deltas_ribbon(obj,original_anim_vertices,original_anim_joints,camera,smooth_window,full_body=False,camera_coord=False):
	vertices = [x.co for x in obj.data.vertices]
	n_vertices = len(vertices)

	frame_start = math.inf
	frame_end = 0

	keyframe_frames = get_keyframe_frames(obj)
	if len(keyframe_frames) > 0:
		frame_start = keyframe_frames[0]
		frame_end = keyframe_frames[-1]

	print(camera.type)
	keyframe_frames = get_keyframe_frames(camera)
	if len(keyframe_frames) > 0:
		frame_start = min(keyframe_frames[0],frame_start)
		frame_end = max(keyframe_frames[-1], frame_end)

	faces = [[x_id for x_id in obj.data.polygons[i].vertices] for i in range(len(obj.data.polygons))]

	animation_deltas = {}
	
	for mod in obj.modifiers:
		if mod.type == "ARMATURE":
			bone_names = [b.name for b in mod.object.data.bones]

			vertex_group_names = [g.name for g in obj.vertex_groups]
			vertices_ids_in_groups = [[] for group in obj.vertex_groups]
			weights_in_groups = [[] for group in obj.vertex_groups]
			for v in obj.data.vertices:
				for g in v.groups:
					vertices_ids_in_groups[g.group].append(v.index)
					weights_in_groups[g.group].append(g.weight)

	wm = bpy.context.window_manager
	wm.progress_begin(0,frame_end-frame_start)
	for frame in range(frame_start,frame_end+1):
		print(f"Computing delta for frame {frame}")
		wm.progress_update(frame)
		bpy.context.scene.frame_set(frame)

		centroid = np.sum(original_anim_vertices[frame],axis=0)/n_vertices
		if frame != frame_end:
			centroid_velocity = np.sum(original_anim_vertices[frame+1],axis=0)/n_vertices - centroid
		else:
			centroid_velocity = centroid - np.sum(original_anim_vertices[frame-1],axis=0)/n_vertices

		centroid_velocity /= norm(centroid_velocity)
		# print(centroid_velocity)

		animation_deltas[frame] = (original_anim_vertices[frame]-centroid) @ centroid_velocity

		# animation_deltas[frame] = []
		# for i in range(n_vertices):
			# animation_deltas[frame].append(np.dot(-obj.data.vertices[i].normal,centroid_velocity))

		max_delta = max(animation_deltas[frame])
		animation_deltas[frame] = animation_deltas[frame]/max_delta

		if full_body:
			continue

		# If an armature is found, we replace the deltas of vertices attached to a bone by considering them as a single rigid object
		# Vertices not attached to any bones will keep the global deltas computed above
		for mod in obj.modifiers:
			if mod.type == "ARMATURE":
				for o in bpy.context.scene.objects:
					o.select_set(False)
				
				armature = mod.object
				armature.select_set(True)

				animation_deltas[frame] = [0 for i in range(n_vertices)]

				still_bones = []
				deltas_groups = {}
				max_at_joint = {}
				max_body_part = {}
				colinear_weights_groups = {}
				w0_array_group = {}
				w1_array_group = {}

				for (group_index,vertices_ids) in enumerate(vertices_ids_in_groups):
					vertices_group = np.take(original_anim_vertices[frame], vertices_ids, axis=0)
					if len(vertices_group) == 0:
						continue

					n_vertices_group = len(vertices_group)
					bone_name = obj.vertex_groups[group_index].name

					if bone_name not in bone_names:
						continue

					bone = armature.data.bones[bone_name]

					joints = original_anim_joints[frame][bone_name]

					if frame != frame_end:
						joints_velocities = [original_anim_joints[frame+1][bone_name][0] - joints[0], original_anim_joints[frame+1][bone_name][1] - joints[1]]
					else:
						joints_velocities = [joints[0] - original_anim_joints[frame-1][bone_name][0], joints[1] - original_anim_joints[frame-1][bone_name][1]]

					# joints_velocities = [(joints_velocities[0]+joints_velocities[1])/2,(joints_velocities[0]+joints_velocities[1])/2]

					if np.all(joints_velocities[0] == 0) and np.all(joints_velocities[1] == 0):
						still_bones.append(bone_name)
						continue

					zero_velocity = False
					if norm(joints_velocities[0]) == 0:
						j0 = joints_velocities[0]
						zero_velocity = True
					else:
						j0 = joints_velocities[0]/norm(joints_velocities[0])
					if norm(joints_velocities[1]) == 0:
						j1 = joints_velocities[1]
						zero_velocity = True
					else:
						j1 = joints_velocities[1]/norm(joints_velocities[1])

					joints_velocities = [j0,j1]


					# joints_velocities = [joints_velocities[0]/norm(joints_velocities[0]) if norm(joints_velocities[0]) != 0 else joints_velocities[0],joints_velocities[1]/norm(joints_velocities[1]) if norm(joints_velocities[1]) != 0 else joints_velocities[1]]

					omega = np.arccos(dot(joints_velocities[0],joints_velocities[1])) if not zero_velocity else 0
					sin_omega = np.sin(omega)

					bone_length = norm(joints[1] - joints[0])
					bone_axis = (joints[1] - joints[0])/bone_length

					# interpolation_weights = []
					# projected = joints[0] + np.resize((vertices_group-joints[0]) @ bone_axis,(n_vertices_group,1)) * bone_axis
					projected = joints[0] + ((vertices_group-joints[0]) @ bone_axis)[:,np.newaxis] * bone_axis
					d1 = np.linalg.norm(joints[1]-projected,axis=1)/bone_length
					sign_d1 = np.dot(joints[1]-projected,joints[1]-joints[0])
					sign_d1 /= np.abs(sign_d1)
					d1 *= sign_d1
					w0_array = smooth_step_array(d1)
					w1_array = 1-w0_array

					if sin_omega > 0.1:
						# projected_velocity = np.resize(np.sin(w0_array*omega)/sin_omega,(n_vertices_group,1)) * joints_velocities[0] + np.resize(np.sin(w1_array*omega)/sin_omega,(n_vertices_group,1)) * joints_velocities[1]
						projected_velocity = (np.sin(w0_array*omega)/sin_omega)[:,np.newaxis] * joints_velocities[0] + (np.sin(w1_array*omega)/sin_omega)[:,np.newaxis] * joints_velocities[1]
					else:
						# projected_velocity = np.resize(w0_array,(n_vertices_group,1)) * joints_velocities[0] + np.resize(w1_array,(n_vertices_group,1)) * joints_velocities[1]
						projected_velocity = w0_array[:,np.newaxis] * joints_velocities[0] + w1_array[:,np.newaxis] * joints_velocities[1]

					bax_dot_projectedvel = projected_velocity @ bone_axis
					# ribbon_normal = projected_velocity - (np.resize(bax_dot_projectedvel,(n_vertices_group,1)) * bone_axis)
					ribbon_normal = projected_velocity - (bax_dot_projectedvel[:,np.newaxis] * bone_axis)
					# ribbon_normal /= np.resize(np.linalg.norm(ribbon_normal,axis=1),(n_vertices_group,1))
					ribbon_normal /= np.linalg.norm(ribbon_normal,axis=1)[:,np.newaxis]

					# if frame == 9:
					# 	vertices = vertices_group
					# 	pi = vertices-np.sum((vertices-joints[0])*ribbon_normal,axis=1)[:,np.newaxis]*ribbon_normal
					# 	add_mesh_to_scene(f"ribbon_{obj.name}",verts=pi,edges=[],faces=faces)

					deltas_ribbon = np.nan_to_num(np.sum((vertices_group - joints[0])*ribbon_normal,axis=1))

					colinear_weights = 1-np.abs(bax_dot_projectedvel)**2
					# colinear_weights = np.ones(len(bax_dot_projectedvel))

					# interpolation_weights = np.stack((w0_array,w1_array),axis=1)

					deltas_groups[bone_name] = deltas_ribbon

					max_delta = np.max(np.abs(deltas_ribbon))
					if original_anim_joints[frame][bone_name][2].name != bone_name:
						parent_name = original_anim_joints[frame][bone_name][2].parent.name
						child_name = original_anim_joints[frame][bone_name][2].name
						max_at_joint[parent_name] = max_delta if not parent_name in max_at_joint.keys() else max(max_at_joint[parent_name],max_delta)
						max_at_joint[child_name] = max_delta if not child_name in max_at_joint.keys() else max(max_at_joint[child_name],max_delta)
					else:
						parent_name = f"{'_' if bone.parent is None else bone.parent.name}"
						child_name = bone_name
						max_at_joint[parent_name] = max_delta if not parent_name in max_at_joint.keys() else max_at_joint[parent_name] + max_delta
						max_at_joint[child_name] = max_delta if not child_name in max_at_joint.keys() else max_at_joint[child_name] + max_delta

					max_body_part[bone_name] = max_delta

					colinear_weights_groups[bone_name] = colinear_weights

					w0_array_group[bone_name] = w0_array
					w1_array_group[bone_name] = w1_array

				for (group_index,vertices_ids) in enumerate(vertices_ids_in_groups):
					weights_group = weights_in_groups[group_index]
					n_vertices_group = len(vertices_ids)
					if (n_vertices_group) == 0:
						continue

					bone_name = obj.vertex_groups[group_index].name

					if bone_name not in bone_names:
						continue

					if bone_name in still_bones:
						continue

					bone = armature.data.bones[bone_name]

					closest_kept_parent = original_anim_joints[frame][bone_name][2]
					if bone_name != closest_kept_parent.name:
						max_parent_joint = max_at_joint[f"{closest_kept_parent.parent.name}"]/(len(closest_kept_parent.parent.children)+1)
						max_child_joint = max_at_joint[closest_kept_parent.name]


					else:
						if bone.parent is None:
							max_parent_joint = max_at_joint["_"]
						else:
							max_parent_joint = max_at_joint[f"{bone.parent.name}"]/(len(bone.parent.children)+1)

						if bone.children is None or np.all([original_anim_joints[frame][c.name][2].name != c.name for c in bone.children]):
							max_child_joint = max_at_joint[bone_name]
						else:
							n_children = sum([b.name in vertex_group_names for b in bone.children])
							max_child_joint = max_at_joint[bone_name]/(n_children+1)


					for i in range(n_vertices_group):
						max_delta = w0_array_group[bone_name][i] * max_parent_joint + w1_array_group[bone_name][i] * max_child_joint
						# max_delta = max_body_part[bone_name]

						animation_deltas[frame][vertices_ids[i]] += colinear_weights_groups[bone_name][i] * weights_group[i] * (deltas_groups[bone_name][i]/max_delta)
						# animation_deltas[frame][vertices_ids[i]] += weights_group[i] * (deltas_groups[bone_name][i]/max_delta)
						# animation_deltas[frame][vertices_ids[i]] += colinear_weights_groups[bone_name][i] * weights_group[i] * deltas_groups[bone_name][i]
						# animation_deltas[frame][vertices_ids[i]] += colinear_weights_groups[bone_name][i] * deltas_groups[bone_name][i]
				
	wm.progress_end()

	animation_deltas = temporal_smooth_delta(animation_deltas,smooth_window,frame_start,frame_end,n_vertices)
	# print(max(animation_deltas[6]))

	return animation_deltas