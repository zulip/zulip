"""
$ python ./tools/js-dep-visualizer.py
$ dot -Tpng var/zulip-deps.dot -o var/zulip-deps.png
"""

import os
import re
import sys

from typing import Any, Dict, List

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, ROOT_DIR)
from tools.lib.graph import Graph, make_dot_file

JS_FILES_DIR = os.path.abspath(os.path.join(ROOT_DIR, 'static/js'))
OUTPUT_FILE_PATH = os.path.abspath(os.path.join(ROOT_DIR, 'var/zulip-deps.dot'))

modules = [] # type: List[Dict[str, Any]]
for js_file in os.listdir(JS_FILES_DIR):
    name = js_file[:-3] # remove .js
    file_path = os.path.abspath(os.path.join(JS_FILES_DIR, js_file))

    if os.path.isfile(file_path) and js_file != '.eslintrc.json':
        modules.append(dict(
            filename=js_file,
            name=name,
            path=file_path,
            regex=re.compile('[^_]{}\.\w+\('.format(name))
        ))

tuples = set()
for module in modules:

    other_modules = filter(lambda x: x['name'] != module['name'], modules)

    with open(module['path']) as f:
        module_content = f.read()
        for other_module in other_modules:
            dependencies = re.findall(other_module['regex'], module_content)
            if dependencies:
                parent = module['name']
                child = other_module['name']
                tup = (parent, child)
                if tup == ('stream_data', 'subs'):
                    continue # parsing mistake due to variable called "subs"
                tuples.add(tup)

# print(tuples)
graph = Graph(*tuples)
tricky_modules = [
    'blueslip',
    'channel',
    'filter',
    'hashchange',
    'message_store',
    'narrow',
    'popovers',
    'reload',
    'resize',
    'server_events', # has restart code
    'socket',
    'stream_color',
    'ui',
    'zulip', # zulip.com false positives
]
for node in tricky_modules:
    graph.remove(node)
graph.remove_exterior_nodes()
buffer = make_dot_file(graph)

with open(OUTPUT_FILE_PATH, 'w') as f:
    f.write(buffer)
