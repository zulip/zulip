# -*- coding: utf-8 -*-
import os
import filecmp
from six import text_type

def compare_files_if_exist(file1, file2):
    # type: (text_type, text_type) -> bool
    return os.path.exists(file1) and os.path.exists(file2) and filecmp.cmp(file1, file2)
