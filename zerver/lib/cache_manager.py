import os
import time
import json
import re

from typing import Any, Dict, Tuple, List
from zerver.lib.cache_files import include, normalize_path, current_dir, PRODUCTION

DATA = {}  # type: Dict[str, Any]
CACHE_FILES = {}  # type: Dict[str, Any]
CACHE_VERSION = 0

# include files to cache here
# file path must be relative to zulip folder
# don't add .html, or any other files
# that is not required for quick page load
# include files for production, dev velow
# you can use glob patterns
if PRODUCTION:
    prod_cache_files = [  # nocoverage
        'static/webpack-bundles/common.*.js',
        'static/min/app.*.js',
        'static/min/common.*.css',
        'static/generated/emoji/google_sprite.css',
        'static/min/app.*.css',
        'static/third/fontawesome/fontawesome-webfont*',
        'static/node_modules/katex/dist/fonts/KaTeX_Main-Regular-*.woff2',
        'static/webpack-bundles/translations-*.js',
        'static/webpack-bundles/katex-*.js',
        'static/generated/emoji/images/emoji/unicode/*.png'
    ]  # type: List[str]
    CACHE_FILES.update(include(prod_cache_files))  # nocoverage
else:
    dev_cache_files = [  # nocoverage
        'static/js/zulip.js',
        'static/js/zulip.css',
        'static/css/zulip.css',
        'static/js/*.js',
        'static/css/*.css'
    ]  # type: List[str]
    CACHE_FILES.update(include(dev_cache_files))  # nocoverage

cache_file_path = os.path.join(current_dir, 'cache_version.json')

# add inital modification time (mtime) if needed or
# filter out odd files
for file_path, modification_time in CACHE_FILES.items():
    file_name = os.path.basename(file_path)
    ext = file_name.split('.')

    if ext == 'html':
        del CACHE_FILES[file_path]  # nocoverage

    if modification_time == '':
        normalized_path = normalize_path(file_path)
        CACHE_FILES[file_path] = os.path.getmtime(normalized_path)

def read_version_file() -> Dict[str, Any]:
    with open(cache_file_path, 'r') as cache_file:
        data = json.load(cache_file)
    return data

def write_version_file(data: Dict[str, Any]) -> None:
    with open(cache_file_path, 'w') as cache_file:
        json.dump(data, cache_file)

def check_if_modified(file_path: str, modification_time: float) -> Tuple[bool, Any]:
    file_path = normalize_path(file_path)
    old_mtime = time.gmtime(modification_time)
    float_mtime = os.path.getmtime(file_path)
    new_mtime = time.gmtime(float_mtime)

    if old_mtime != new_mtime:
        return (True, float_mtime)
    else:
        return (False, None)

def get_cache_files_array() -> str:
    files_array = 'var cacheFiles = ['
    for file_url in CACHE_FILES.items():
        files_array += '"{}", '.format(file_url[0])
    files_array = re.sub(r',\s$', '', files_array)
    files_array += ']'
    return files_array

def update_version() -> int:
    global DATA, CACHE_VERSION
    CACHE_VERSION += 1
    DATA['cache_version'] = CACHE_VERSION
    write_version_file(DATA)
    return CACHE_VERSION

def sync_data() -> None:
    global DATA, CACHE_FILES, CACHE_VERSION
    should_update = False
    for file_name in list(CACHE_FILES):
        if file_name not in DATA['cache_files']:
            DATA['cache_files'][file_name] = CACHE_FILES[file_name]  # nocoverage
            should_update = True  # nocoverage

    for file_name in list(DATA['cache_files']):
        if file_name not in CACHE_FILES:
            del DATA['cache_files'][file_name]  # nocoverage
            should_update = True  # nocoverage

    if should_update:
        update_version()  # nocoverage

def check() -> None:
    global DATA, CACHE_FILES, CACHE_VERSION
    should_update = False
    for file_path, modification_time in DATA['cache_files'].items():
        updated, new_mtime = check_if_modified(file_path, modification_time)

        if updated:
            should_update = True
            CACHE_FILES[file_path] = new_mtime
            DATA['cache_files'][file_path] = new_mtime

    if should_update:
        update_version()

if not os.path.exists(cache_file_path):
    DATA = {
        'cache_version': CACHE_VERSION,
        'cache_files': CACHE_FILES
    }  # nocoverage
    write_version_file(DATA)  # nocoverage
else:
    DATA = read_version_file()
    sync_data()
    check()
