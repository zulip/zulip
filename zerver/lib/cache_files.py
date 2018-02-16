import os
import re
import glob
import configparser

from typing import List, Dict

config_file = configparser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")
PRODUCTION = config_file.has_option('machine', 'deploy_type')

current_dir = os.path.dirname(os.path.abspath(__file__))
zulip_dir = os.path.abspath(os.path.join(current_dir, '../../'))

def normalize_path(file_path: str) -> str:
    file_path = re.sub(r'^\/', '', file_path)
    normalized_path = os.path.join(zulip_dir, file_path)
    return normalized_path

# fix the file path and make it so that they are
# relative to zulip directory
def fix_file_path(file_path: str) -> str:
    return file_path.replace(zulip_dir, '')


def include(file_patterns: List[str]) -> Dict[str, str]:
    cache_files = {}  # type: Dict[str, str]
    for pattern in file_patterns:  # nocoverage
        normalize_pattern = normalize_path(pattern)
        possible_files = glob.glob(normalize_pattern)

        for file_name in possible_files:
            file_name = fix_file_path(file_name)
            cache_files[file_name] = ''

    return cache_files
