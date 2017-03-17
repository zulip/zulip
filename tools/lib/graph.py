from collections import defaultdict

from typing import List, Set, Tuple

class Graph(object):
    def __init__(self, *tuples):
        # type: (Tuple[str, str]) -> None
        self.children = defaultdict(list) # type: defaultdict[str, List[str]]
        self.parents = defaultdict(list) # type: defaultdict[str, List[str]]
        self.nodes = set() # type: Set[str]

        for parent, child in tuples:
            self.parents[child].append(parent)
            self.children[parent].append(child)
            self.nodes.add(parent)
            self.nodes.add(child)

    def remove_exterior_nodes(self):
        # type: () -> None
        still_work_to_do = True
        while still_work_to_do:
            still_work_to_do = False # for now
            for node in self.nodes:
                if self.parents[node] and self.children[node]:
                    # we are an interior node still
                    continue
                self.remove(node)
                still_work_to_do = True
                break

    def remove(self, node):
        # type: (str) -> None
        for parent in self.parents[node]:
            self.children[parent].remove(node)
        for child in self.children[node]:
            self.parents[child].remove(node)
        self.nodes.remove(node)

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
    graph = Graph(
        ('x', 'a'),
        ('a', 'b'),
        ('b', 'c'),
        ('c', 'a'),
        ('c', 'd'),
        ('d', 'e'),
        ('e', 'f'),
        ('e', 'g'),
    )
    graph.remove_exterior_nodes()

    s = make_dot_file(graph)
    open('zulip-deps.dot', 'w').write(s)

if __name__ == '__main__':
    test()
