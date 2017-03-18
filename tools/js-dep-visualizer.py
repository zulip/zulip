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
    other_modules = [x for x in modules if x['name'] != module['name']]

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

IGNORE_TUPLES = [
    # We ignore the following tuples to de-clutter the graph, since there is a
    # pretty clear roadmap on how to break the dependencies.  You can comment
    # these out to see what the "real" situation looks like now, and if you do
    # the work of breaking the dependency, you can remove it.

    ('typeahead_helper', 'composebox_typeahead'), # PR 4121
    ('typeahead_helper', 'compose'), # PR 4121
    ('typeahead_helper', 'subs'), # PR 4121

    ('stream_data', 'narrow'), # split out narrow.by_foo functions

    ('stream_data', 'stream_color'), # split out stream_color data/UI
    ('stream_color', 'tab_bar'), # only one call
    ('stream_color', 'subs'), # only one call

    ('search', 'search_suggestion'), # move handler into search_suggestion

    ('unread', 'narrow'), # create narrow_state.js

    ('navigate', 'stream_list'), # move cycle_stream into stream_list.js

    # This one is kind of tricky, but basically we want to split all the basic
    # code out of both of these modules that's essentially just string manipulation.
    ('narrow', 'hashchange'),

    ('composebox_typeahead', 'compose'), # introduce compose_state.js

    # This one might require some work, but the idea is to split out something
    # like narrow_state.js.
    ('pm_list', 'narrow'),

    ('settings', 'subs'), # not much to fix, can call stream_data directly, maybe

    ('modals', 'subs'), # add some kind of onClose mechanism in new modals.open

    ('channel', 'reload'), # just one call to fix somehow
    ('compose', 'reload'), # use channel stuff more directly?

    ('settings', 'muting_ui'), # inline call or split out muting_settings.js

    ('resize', 'navigate'), # split out scroll.js
]

for tuple in IGNORE_TUPLES:
    tuples.discard(tuple)


# print(tuples)
graph = Graph(*tuples)
ignore_modules = [
    # some are really tricky
    'message_store',
    'popovers',
    'server_events', # has restart code
    'unread_ui',
    'ui', # initializes all the other widgets

    # some are just not very core:
    'drafts',
    'notifications',
    'stream_popover',
]
for node in ignore_modules:
    graph.remove(node)
graph.remove_exterior_nodes()
buffer = make_dot_file(graph)

with open(OUTPUT_FILE_PATH, 'w') as f:
    f.write(buffer)
