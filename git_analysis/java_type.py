""" Defines the hierarchy of Java units of code - a package(file) may include one or more
    classes(/enums/interfaces), each may have further classes or methods.
"""

from __future__ import annotations
from typing import NamedTuple, List, Optional, Union, Iterator
from enum import IntEnum, auto
from functools import partial

class HierarchyType(IntEnum):
    package = auto()
    # class, interface or enum
    type_def = auto() 
    # also covers constructors and static functions
    method = auto()
    

class JavaHierarchy:
    start: int
    end: int
    name: str
    members: List[JavaHierarchy]
    parent: Optional[JavaHierarchy]
    kind: HierarchyType
    __slots__ = ['start', 'end', 'name', 'kind', 'members', 'parent']

    def __init__(self, name: str, kind: HierarchyType, start: int, end: int, parent: Optional[JavaHierarchy] = None,
                 members: Optional[List[JavaHierarchy]] = None):
        self.name = name
        self.kind = kind
        self.start = start
        self.end = end
        self.parent = parent
        self.members = [] if members is None else members


JavaFile = partial(JavaHierarchy, kind=HierarchyType.package)
JavaClass = partial(JavaHierarchy, kind=HierarchyType.type_def)
JavaMethod = partial(JavaHierarchy, kind=HierarchyType.method)


def tree_dfs_preorder(tree: JavaHierarchy) -> Iterator[JavaHierarchy]:
    """ Traverses the Java hierarchy in a DFS preorder (a topological sort), note that
        this ordering goes over the Java hierarchy elements by the order in which their declarations appear.
    """
    stack = [tree]
    while len(stack) > 0:
        parent = stack.pop()
        if parent.members:
            stack.extend(reversed(parent.members))
        yield parent



class PosToJavaUnitMatcher:
    """ Responsible for matching byte positions in the original file, to
        the Java hierarchy that they belong to. Positions are assumed to be given in an ascending order"""
    def __init__(self, root: JavaHierarchy):
        self._it = tree_dfs_preorder(root)
        self._cur = next(self._it)
        self._next = next(self._it, None)

    def find(self, pos: int) -> JavaHierarchy:
        assert pos >= self._cur.start, "Byte positions must be given in weakly increasing order"

        while self._next is not None and pos >= self._next.start:
            self._cur = self._next
            self._next = next(self._it, None)

        # If the position is beyond the current declaration, but before the next one(
        # or the next one doesn't exist) - e.g, a change between two adjacent methods,
        # or after the last method, then we must belong to the parent (e.g, the class
        # containing them)
        candidate = self._cur
        while pos >= candidate.end and candidate.parent is not None:
            candidate  = candidate.parent
        return candidate

    

def test_dfs():
    tree = JavaFile(start=0, end=200, name="F", members=[])
    c1 = JavaClass(
            start=1, end=100, name="C1", kind="class", members=[], parent=tree)
    c1.members.extend([
        JavaMethod(start=5, end=40, name="C1M1", parent=c1),
        JavaMethod(start=41, end=80, name="C1M2", parent=c1)
    ])
    c2 = JavaClass(
            start=105, end=180, name="C2", kind="class", members=[], parent=tree)
    c2.members.extend([JavaMethod(start=110, end=140, name="C2M1", parent=c2),
                        JavaMethod(start=150, end=180, name="C2M2", parent=c2)
                        ])
    tree.members.extend([c1,c2])
    names = [h.name for h in tree_dfs_preorder(tree)]
    assert names == ["F", "C1", "C1M1", "C1M2", "C2", "C2M1", "C2M2"]

    finder = PosToJavaUnitMatcher(tree)
    assert finder.find(0).name == "F"
    assert finder.find(1).name == "C1"
    assert finder.find(40).name == "C1"
    assert finder.find(41).name == "C1M2"
    assert finder.find(85).name == "C1"
    assert finder.find(100).name == "F"
    assert finder.find(120).name == "C2M1"
    assert finder.find(160).name == "C2M2"
    assert finder.find(180).name == "F"