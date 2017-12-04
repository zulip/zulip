import os
import subprocess
import logging
import difflib

def diff_strings(output: str, expected_output: str) -> str:

    mdiff_path = "frontend_tests/zjsunit/mdiff.js"
    if not os.path.isfile(mdiff_path):  # nocoverage
        logging.error("Cannot find mdiff for markdown diff rendering")
        return None

    command = ['node', mdiff_path, output, expected_output]
    diff = subprocess.check_output(command).decode('utf-8')
    return diff
