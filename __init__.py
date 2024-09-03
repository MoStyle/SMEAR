# SPDX-FileCopyrightText: 2024 Jean Basset <jean.basset@inria.fr>

# SPDX-License-Identifier: CECILL-2.1


bl_info = {
	"name":"Smear",
	"author": "Jean Basset",
	"version": (1, 1),
	"blender": (4,2,0),
	"category": "Animation",
}

import bpy
from . import install_dependencies
install_dependencies.install_all()
from . import smear_control_panel 

import imp
imp.reload(smear_control_panel)

node_trees = ["animationTiming","applyDeltas","catmullParametersAggregated","catmullRomInterp","displaceAndClamp","fromCameraCoord","getFloatAttributeAtFrame","getSpeed","idsRange","maxNormalize","pastFutureWeights","smoothedVoronoiNoise","speedFactor"]

def register():
	smear_control_panel.register()

def unregister():
	smear_control_panel.unregister()
	rootNodeTree = bpy.data.node_groups['Smear Frames Controler']
	nodesToDelete = ['Smear Frames Controler']
	for node in bpy.data.node_groups:
		if rootNodeTree.contains_tree(node):
			nodesToDelete.append(node.name)

	for node in bpy.data.node_groups:
		if sum([node.name.startswith(n) for n in nodesToDelete]) > 0:
			bpy.data.node_groups.remove(node)

if __name__ == "__main__":
	register()