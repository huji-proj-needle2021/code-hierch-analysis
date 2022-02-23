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

    def included(self) -> List[HierarchyType]:
        if self == HierarchyType.method:
            return [HierarchyType.method, HierarchyType.type_def, HierarchyType.package]
        if self == HierarchyType.type_def:
            return [HierarchyType.type_def, HierarchyType.package]
        return [HierarchyType.package]
    

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

    def iterate_up_to_parents(self) -> Iterator[JavaHierarchy]:
        cur = self
        yield self
        while cur.parent is not None:
            cur = cur.parent
            yield cur

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
    hierarchies: Tuple[Tuple[HierarchyType, str], ...]
    __slots__ = ['hierarchies']

    def __init__(self, hierarchies: Tuple[Tuple[HierarchyType, str], ...]):
        self.hierarchies = hierarchies

    @staticmethod
    def from_bottommost_hierarchy(bottommost_hierarchy: JavaHierarchy):
        return JavaIdentifier(tuple((hierch.kind, hierch.name)
                                    for hierch in bottommost_hierarchy.iterate_up_to_parents()))

    @property
    def identifier_type(self) -> HierarchyType:
        return self.hierarchies[0][0]

    def __str__(self) -> str:
        return ".".join(tup[1] for tup in reversed(self.hierarchies))
    
    def __repr__(self) -> str:
        return repr(self.hierarchies)

    def __hash__(self) -> int:
        return hash(self.hierarchies)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, JavaIdentifier):
            return self.hierarchies == o.hierarchies
        return False
    

    def as_method(self) -> Optional[JavaIdentifier]:
        if self.identifier_type == HierarchyType.method:
            return self
        return None
    
    def as_class(self) -> Optional[JavaIdentifier]:
        if self.identifier_type == HierarchyType.type_def:
           return self
        elif self.identifier_type == HierarchyType.package:
            return None
        return JavaIdentifier(self.hierarchies[1:])

    def as_package(self) -> JavaIdentifier:
        return JavaIdentifier((self.hierarchies[-1],))
