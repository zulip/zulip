
from collections import defaultdict

from typing import Callable, DefaultDict, Iterator, List, Optional, Set, Tuple

Edge = Tuple[str, str]
EdgeSet = Set[Edge]

class Graph:
    def __init__(self, tuples):
        # type: (EdgeSet) -> None
        self.children = defaultdict(list)  # type: DefaultDict[str, List[str]]
        self.parents = defaultdict(list)  # type: DefaultDict[str, List[str]]
        self.nodes = set()  # type: Set[str]

        for parent, child in tuples:
            self.parents[child].append(parent)
            self.children[parent].append(child)
            self.nodes.add(parent)
            self.nodes.add(child)

    def copy(self):
        # type: () -> 'Graph'
        return Graph(self.edges())

    def num_edges(self):
        # type: () -> int
        return len(self.edges())

    def minus_edge(self, edge):
        # type: (Edge) -> 'Graph'
        edges = self.edges().copy()
        edges.remove(edge)
        return Graph(edges)

    def edges(self):
        # type: () -> EdgeSet
        s = set()
        for parent in self.nodes:
            for child in self.children[parent]:
                s.add((parent, child))
        return s

    def remove_exterior_nodes(self):
        # type: () -> None
        still_work_to_do = True
        while still_work_to_do:
            still_work_to_do = False  # for now
            for node in self.nodes:
                if self.is_exterior_node(node):
                    self.remove(node)
                    still_work_to_do = True
                    break

    def is_exterior_node(self, node):
        # type: (str) -> bool
        parents = self.parents[node]
        children = self.children[node]
        if not parents:
            return True
        if not children:
            return True
        if len(parents) > 1 or len(children) > 1:
            return False

        # If our only parent and child are the same node, then we could
        # effectively be collapsed into the parent, so don't add clutter.
        return parents[0] == children[0]

    def remove(self, node):
        # type: (str) -> None
        for parent in self.parents[node]:
            self.children[parent].remove(node)
        for child in self.children[node]:
            self.parents[child].remove(node)
        self.nodes.remove(node)

    def report(self):
        # type: () -> None
        print('parents/children/module')
        tups = sorted([
            (len(self.parents[node]), len(self.children[node]), node)
            for node in self.nodes])
        for tup in tups:
            print(tup)

def best_edge_to_remove(orig_graph, is_exempt):
    # type: (Graph, Callable[[Edge], bool]) -> Optional[Edge]
    # expects an already reduced graph as input

    orig_edges = orig_graph.edges()

    def get_choices():
        # type: () -> Iterator[Tuple[int, Edge]]
        for edge in orig_edges:
            if is_exempt(edge):
                continue
            graph = orig_graph.minus_edge(edge)
            graph.remove_exterior_nodes()
            size = graph.num_edges()
            yield (size, edge)

    choices = list(get_choices())
    if not choices:
        return None
    min_size, best_edge = min(choices)
    if min_size >= orig_graph.num_edges():
        raise Exception('no edges work here')
    return best_edge

def make_dot_file(graph):
    # type: (Graph) -> str
    buffer = 'digraph G {\n'
    for node in graph.nodes:
        buffer += node + ';\n'
        for child in graph.children[node]:
            buffer += '{} -> {};\n'.format(node, child)
    buffer += '}'
    return buffer

def test():
    # type: () -> None
    graph = Graph(set([
        ('x', 'a'),
        ('a', 'b'),
        ('b', 'c'),
        ('c', 'a'),
        ('c', 'd'),
        ('d', 'e'),
        ('e', 'f'),
        ('e', 'g'),
    ]))
    graph.remove_exterior_nodes()

    s = make_dot_file(graph)
    open('zulip-deps.dot', 'w').write(s)

if __name__ == '__main__':
    test()
