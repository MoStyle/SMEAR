# SPDX-FileCopyrightText: 2024 Jean Basset <jean.basset@inria.fr>

# SPDX-License-Identifier: CECILL-2.1

import imp
import pip

def is_installed(module):
	try:
		imp.find_module(module)
		return True
	except ImportError:
		return False


def install(module):
	if not is_installed(module):
		pip.main(['install',module,"--user"])


def install_all():
	install("numpy")