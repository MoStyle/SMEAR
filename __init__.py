# SPDX-FileCopyrightText: 2024 Jean Basset <jean.basset@inria.fr>

# SPDX-License-Identifier: CECILL-2.1


bl_info = {
	"name":"Smear",
	"author": "Jean Basset",
	"version": (1, 1, 2),
	"blender": (4,2,0),
	"category": "Animation",
}

import bpy
from . import smear_control_panel 

def register():
	smear_control_panel.register()

def unregister():
	smear_control_panel.unregister()

if __name__ == "__main__":
	register()
