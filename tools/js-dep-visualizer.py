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

JS_FILES_DIR = os.path.join(ROOT_DIR, 'static/js')
OUTPUT_FILE_PATH = os.path.relpath(os.path.join(ROOT_DIR, 'var/zulip-deps.dot'))

names = set()
modules = [] # type: List[Dict[str, Any]]
for js_file in os.listdir(JS_FILES_DIR):
    if not js_file.endswith('.js'):
        continue
    name = js_file[:-3] # remove .js
    path = os.path.join(JS_FILES_DIR, js_file)
    names.add(name)
    modules.append(dict(
        name=name,
        path=path,
        regex=re.compile('[^_]{}\.\w+\('.format(name))
    ))

COMMENT_REGEX = re.compile('\s+//')
REGEX = re.compile('[^_](\w+)\.\w+\(')

tuples = set()
for module in modules:
    parent = module['name']

    with open(module['path']) as f:
        for line in f:
            if COMMENT_REGEX.match(line):
                continue
            if 'subs.forEach' in line:
                continue
            m = REGEX.search(line)
            if not m:
                continue
            for child in m.groups():
                if (child in names) and (child != parent):
                    tup = (parent, child)
                    tuples.add(tup)

IGNORE_TUPLES = [
    # We ignore the following tuples to de-clutter the graph, since there is a
    # pretty clear roadmap on how to break the dependencies.  You can comment
    # these out to see what the "real" situation looks like now, and if you do
    # the work of breaking the dependency, you can remove it.

    ('echo', 'message_events'), # do something slimy here
    ('echo', 'ui'),

    ('stream_data', 'narrow'), # split out narrow.by_foo functions
    ('activity', 'narrow'),

    ('subs', 'narrow'), # data functions
    ('subs', 'compose'), # data functions

    ('narrow', 'ui'), # just three functions

    ('stream_data', 'stream_color'), # split out stream_color data/UI
    ('stream_color', 'tab_bar'), # only one call
    ('stream_color', 'subs'), # only one call

    ('subs', 'stream_events'), # see TODOs related to mark_{un,}subscribed

    ('subs', 'hashchange'), # modal stuff

    ('message_store', 'compose'), # split out compose_data

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
    ('resize', 'popovers'), # only three interactions

]

for tup in IGNORE_TUPLES:
    try:
        tuples.remove(tup)
    except KeyError:
        print('''
            {} no longer needs to be ignored.  Help us celebrate
            by removing it from IGNORE_TUPLES!
        '''.format(tup))
        sys.exit(1)


# print(tuples)
graph = Graph(*tuples)
ignore_modules = [
    'blueslip',
    'message_edit',
    'message_util',
    'modals',
    'notifications',
    'popovers',
    'server_events',
    'stream_popover',
    'topic_list',
    'tutorial',
    'unread_ops',
    'rows', # message_store
]
for node in ignore_modules:
    graph.remove(node)
graph.remove_exterior_nodes()
graph.report()
buffer = make_dot_file(graph)

with open(OUTPUT_FILE_PATH, 'w') as f:
    f.write(buffer)
print()
print('see dot file here: {}'.format(OUTPUT_FILE_PATH))
