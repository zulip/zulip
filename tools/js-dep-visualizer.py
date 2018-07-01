#!/usr/bin/env python3
"""
$ ./tools/js-dep-visualizer.py
$ dot -Tpng var/zulip-deps.dot -o var/zulip-deps.png
"""


import os
import re
import subprocess
import sys
from collections import defaultdict

from typing import Any, DefaultDict, Dict, List, Set, Tuple
Edge = Tuple[str, str]
EdgeSet = Set[Edge]
Method = str
MethodDict = DefaultDict[Edge, List[Method]]


TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, ROOT_DIR)
from tools.lib.graph import (
    Graph,
    make_dot_file,
    best_edge_to_remove,
)

JS_FILES_DIR = os.path.join(ROOT_DIR, 'static/js')
OUTPUT_FILE_PATH = os.path.relpath(os.path.join(ROOT_DIR, 'var/zulip-deps.dot'))
PNG_FILE_PATH = os.path.relpath(os.path.join(ROOT_DIR, 'var/zulip-deps.png'))

def get_js_edges():
    # type: () -> Tuple[EdgeSet, MethodDict]
    names = set()
    modules = []  # type: List[Dict[str, Any]]
    for js_file in os.listdir(JS_FILES_DIR):
        if not js_file.endswith('.js'):
            continue
        name = js_file[:-3]  # remove .js
        path = os.path.join(JS_FILES_DIR, js_file)
        names.add(name)
        modules.append(dict(
            name=name,
            path=path,
            regex=re.compile(r'[^_]{}\.\w+\('.format(name))
        ))

    comment_regex = re.compile(r'\s+//')
    call_regex = re.compile(r'[^_](\w+\.\w+)\(')

    methods = defaultdict(list)  # type: DefaultDict[Edge, List[Method]]
    edges = set()
    for module in modules:
        parent = module['name']

        with open(module['path']) as f:
            for line in f:
                if comment_regex.match(line):
                    continue
                if 'subs.forEach' in line:
                    continue
                m = call_regex.search(line)
                if not m:
                    continue
                for g in m.groups():
                    child, method = g.split('.')
                    if (child not in names):
                        continue
                    if child == parent:
                        continue
                    tup = (parent, child)
                    edges.add(tup)
                    methods[tup].append(method)
    return edges, methods

def find_edges_to_remove(graph, methods):
    # type: (Graph, MethodDict) -> Tuple[Graph, List[Edge]]
    EXEMPT_EDGES = [
        # These are sensible dependencies, so don't cut them.
        ('rows', 'message_store'),
        ('filter', 'stream_data'),
        ('server_events', 'user_events'),
        ('compose_fade', 'stream_data'),
        ('narrow', 'message_list'),
        ('stream_list', 'topic_list',),
        ('subs', 'stream_muting'),
        ('hashchange', 'settings'),
        ('tutorial', 'narrow'),
        ('activity', 'resize'),
        ('hashchange', 'drafts'),
        ('compose', 'echo'),
        ('compose', 'resize'),
        ('settings', 'resize'),
        ('compose', 'unread_ops'),
        ('compose', 'drafts'),
        ('echo', 'message_edit'),
        ('echo', 'stream_list'),
        ('hashchange', 'narrow'),
        ('hashchange', 'subs'),
        ('message_edit', 'echo'),
        ('popovers', 'message_edit'),
        ('unread_ui', 'activity'),
        ('message_fetch', 'message_util'),
        ('message_fetch', 'resize'),
        ('message_util', 'resize'),
        ('notifications', 'tutorial'),
        ('message_util', 'unread_ui'),
        ('muting_ui', 'stream_list'),
        ('muting_ui', 'unread_ui'),
        ('stream_popover', 'subs'),
        ('stream_popover', 'muting_ui'),
        ('narrow', 'message_fetch'),
        ('narrow', 'message_util'),
        ('narrow', 'navigate'),
        ('unread_ops', 'unread_ui'),
        ('narrow', 'unread_ops'),
        ('navigate', 'unread_ops'),
        ('pm_list', 'unread_ui'),
        ('stream_list', 'unread_ui'),
        ('popovers', 'compose'),
        ('popovers', 'muting_ui'),
        ('popovers', 'narrow'),
        ('popovers', 'resize'),
        ('pm_list', 'resize'),
        ('notifications', 'navigate'),
        ('compose', 'socket'),
        ('stream_muting', 'message_util'),
        ('subs', 'stream_list'),
        ('ui', 'message_fetch'),
        ('ui', 'unread_ops'),
        ('condense', 'message_viewport'),
        ('compose_actions', 'compose'),
        ('compose_actions', 'resize'),
        ('settings_streams', 'stream_data'),
        ('drafts', 'hashchange'),
        ('settings_notifications', 'stream_edit'),
        ('compose', 'stream_edit'),
        ('subs', 'stream_edit'),
        ('narrow_state', 'stream_data'),
        ('stream_edit', 'stream_list'),
        ('reactions', 'emoji_picker'),
        ('message_edit', 'resize'),
    ]  # type: List[Edge]

    def is_exempt(edge):
        # type: (Tuple[str, str]) -> bool
        parent, child = edge
        if edge == ('server_events', 'reload'):
            return False
        if parent in ['server_events', 'user_events', 'stream_events',
                      'message_events', 'reload']:
            return True
        if child == 'rows':
            return True
        return edge in EXEMPT_EDGES

    APPROVED_CUTS = [
        ('stream_edit', 'stream_events'),
        ('unread_ui', 'pointer'),
        ('typing_events', 'narrow'),
        ('echo', 'message_events'),
        ('resize', 'navigate'),
        ('narrow', 'search'),
        ('subs', 'stream_events'),
        ('stream_color', 'tab_bar'),
        ('stream_color', 'subs'),
        ('stream_data', 'narrow'),
        ('unread', 'narrow'),
        ('composebox_typeahead', 'compose'),
        ('message_list', 'message_edit'),
        ('message_edit', 'compose'),
        ('message_store', 'compose'),
        ('settings_notifications', 'subs'),
        ('settings', 'settings_muting'),
        ('message_fetch', 'tutorial'),
        ('settings', 'subs'),
        ('activity', 'narrow'),
        ('compose', 'compose_actions'),
        ('compose', 'subs'),
        ('compose_actions', 'drafts'),
        ('compose_actions', 'narrow'),
        ('compose_actions', 'unread_ops'),
        ('drafts', 'compose'),
        ('drafts', 'echo'),
        ('echo', 'compose'),
        ('echo', 'narrow'),
        ('echo', 'pm_list'),
        ('echo', 'ui'),
        ('message_fetch', 'activity'),
        ('message_fetch', 'narrow'),
        ('message_fetch', 'pm_list'),
        ('message_fetch', 'stream_list'),
        ('message_fetch', 'ui'),
        ('narrow', 'ui'),
        ('message_util', 'compose'),
        ('subs', 'compose'),
        ('narrow', 'hashchange'),
        ('subs', 'hashchange'),
        ('navigate', 'narrow'),
        ('navigate', 'stream_list'),
        ('pm_list', 'narrow'),
        ('pm_list', 'stream_popover'),
        ('muting_ui', 'stream_popover'),
        ('popovers', 'stream_popover'),
        ('topic_list', 'stream_popover'),
        ('stream_edit', 'subs'),
        ('topic_list', 'narrow'),
        ('stream_list', 'narrow'),
        ('stream_list', 'pm_list'),
        ('stream_list', 'unread_ops'),
        ('notifications', 'ui'),
        ('notifications', 'narrow'),
        ('notifications', 'unread_ops'),
        ('typing', 'narrow'),
        ('message_events', 'compose'),
        ('stream_muting', 'stream_list'),
        ('subs', 'narrow'),
        ('unread_ui', 'pm_list'),
        ('unread_ui', 'stream_list'),
        ('overlays', 'hashchange'),
        ('emoji_picker', 'reactions'),
    ]

    def cut_is_legal(edge):
        # type: (Edge) -> bool
        parent, child = edge
        if child in ['reload', 'popovers', 'overlays', 'notifications',
                     'server_events', 'compose_actions']:
            return True
        return edge in APPROVED_CUTS

    graph.remove_exterior_nodes()
    removed_edges = list()
    print()
    while graph.num_edges() > 0:
        edge = best_edge_to_remove(graph, is_exempt)
        if edge is None:
            print('we may not be allowing edge cuts!!!')
            break
        if cut_is_legal(edge):
            graph = graph.minus_edge(edge)
            graph.remove_exterior_nodes()
            removed_edges.append(edge)
        else:
            for removed_edge in removed_edges:
                print(removed_edge)
            print()
            edge_str = str(edge) + ','
            print(edge_str)
            for method in methods[edge]:
                print('    ' + method)
            break

    return graph, removed_edges

def report_roadmap(edges, methods):
    # type: (List[Edge], MethodDict) -> None
    child_modules = {child for parent, child in edges}
    module_methods = defaultdict(set)  # type: DefaultDict[str, Set[str]]
    callers = defaultdict(set)  # type: DefaultDict[Tuple[str, str], Set[str]]
    for parent, child in edges:
        for method in methods[(parent, child)]:
            module_methods[child].add(method)
            callers[(child, method)].add(parent)

    for child in sorted(child_modules):
        print(child + '.js')
        for method in module_methods[child]:
            print('    ' + child + '.' + method)
            for caller in sorted(callers[(child, method)]):
                print('        ' + caller + '.js')
            print()
        print()

def produce_partial_output(graph):
    # type: (Graph) -> None
    print(graph.num_edges())
    buffer = make_dot_file(graph)

    graph.report()
    with open(OUTPUT_FILE_PATH, 'w') as f:
        f.write(buffer)
    subprocess.check_call(["dot", "-Tpng", OUTPUT_FILE_PATH, "-o", PNG_FILE_PATH])
    print()
    print('See dot file here: {}'.format(OUTPUT_FILE_PATH))
    print('See output png file: {}'.format(PNG_FILE_PATH))

def run():
    # type: () -> None
    edges, methods = get_js_edges()
    graph = Graph(edges)
    graph, removed_edges = find_edges_to_remove(graph, methods)
    if graph.num_edges() == 0:
        report_roadmap(removed_edges, methods)
    else:
        produce_partial_output(graph)

if __name__ == '__main__':
    run()
