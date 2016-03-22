#!/usr/bin/env python
from __future__ import print_function

import os
import subprocess

def list_files(targets=[]):
    """
    List files tracked by git.
    Returns a list of files which are either in targets or in directories in targets.
    If targets is [], list of all tracked files in current directory is returned.
    """
    cmdline = ['git', 'ls-files'] + targets

    files_gen = (x.strip() for x in subprocess.check_output(cmdline, universal_newlines=True).split('\n'))
    # throw away empty lines and non-files (like symlinks)
    files = list(filter(os.path.isfile, files_gen))

    return files
