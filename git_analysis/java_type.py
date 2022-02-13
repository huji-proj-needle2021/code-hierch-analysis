""" Defines the hierarchy of Java units of code - a package(file) may include one or more
    classes(/enums/interfaces), each may have further classes or methods.

    Includes `JavaHierarchy which is essentially a tree node, and `JavaIdentifier`
    which is a compact representation of said node
"""

from __future__ import annotations
from typing import NamedTuple, List, Optional, Union, Iterator, Tuple
from enum import IntEnum, auto
from functools import partial

class HierarchyType(IntEnum):
    package = auto()
    # class, interface or enum
    type_def = auto() 
    # also covers constructors and static functions
    method = auto()
    

class JavaHierarchy:
    """ A node in our Java parse tree, represents a hierarchy of a java unit of code:
        a package, type definition(class, interface, enum) or a method
        
        Includes the byte position in which the declaration of this hierarchy starts and
        ends, as well as references to member and parent nodes in the hierarchy inferred
        from the parsed file.
    """
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

    def iterate_dfs_preorder(self) -> Iterator[JavaHierarchy]:
        """ Traverses the Java hierarchy in a DFS preorder (a topological sort), note that
            this ordering goes over the Java hierarchy elements by the order in which their declarations appear.
        """
        stack = [self]
        while len(stack) > 0:
            parent = stack.pop()
            if parent.members:
                stack.extend(reversed(parent.members))
            yield parent


JavaFile = partial(JavaHierarchy, kind=HierarchyType.package)
JavaClass = partial(JavaHierarchy, kind=HierarchyType.type_def)
JavaMethod = partial(JavaHierarchy, kind=HierarchyType.method)

class JavaIdentifier:
    """ An identifier to some unit of Java code that corresponds to one or more
        hierarchies in program modularization. For example `com.foo.ClsA.bar`
        is an identifier to method `bar` under `ClsA` belonging to package `com.foo`,
        this class represents such identifier in an object form.
    """

    # Java hierarchy kinds and identifiers, from most specific to most general.
    hierarchies: List[Tuple[HierarchyType, str]]
    __slots__ = ['hierarchies']

    def __init__(self, bottommost_hierarchy: JavaHierarchy):
        self.hierarchies = [(bottommost_hierarchy.kind, bottommost_hierarchy.name)]
        parent = bottommost_hierarchy.parent
        while parent is not None:
            self.hierarchies.append((parent.kind, parent.name))
            parent = parent.parent

    def __str__(self) -> str:
        return ".".join(tup[1] for tup in reversed(self.hierarchies))

    
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
    names = [h.name for h in tree.iterate_dfs_preorder()]
    assert names == ["F", "C1", "C1M1", "C1M2", "C2", "C2M1", "C2M2"]

    assert str(JavaIdentifier(c1)) == "F.C1"
    assert str(JavaIdentifier(c2.members[1])) == "F.C2.C2M2"