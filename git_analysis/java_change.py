""" This file defines a few types needed to represent a change in the Java source code,
    which will act as the items in the itemset algorithm, and a class for matching
    byte positions to the Java hierarchy they belong to.
"""
from typing import NamedTuple, Optional, Tuple, List, Iterable
from enum import IntEnum
from .java_type import JavaHierarchy, JavaIdentifier, HierarchyType, JavaFile, JavaClass, JavaMethod

class PosToJavaUnitMatcher:
    """ Responsible for matching byte positions in the original file, to
        the Java hierarchy that they belong to. Positions are assumed to be given in an ascending order"""

    __slots__ = ['_it', '_cur', '_next']
    def __init__(self, root: JavaHierarchy):
        self._it = root.iterate_dfs_preorder()
        self._cur = next(self._it)
        self._next = next(self._it, None)

    def find(self, pos: int) -> JavaHierarchy:
        """ Finds the most specific Java hierarchy to which the byte at given
            position belongs to. 
        """
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

    def find_range(self, from_pos: int, to_pos: int) -> Iterable[JavaHierarchy]:
        """ Finds the most specific Java hierarchies to which bytes changed
            at the given range belong to. Like `find`, this assumes byte ranges
            are given in monotonically ascending order.
        """
        cur_hierch = self.find(from_pos)
        yield cur_hierch

        while self._next is not None and self._next.start < to_pos:
            yield self._next
            self._cur = self._next
            self._next = next(self._it, None)


class ChangeType(IntEnum):
    """ The kind of change reflected by a git diff line. """
    ADD = 0
    # When a java identifier is deleted and added in the same commit, we consider 
    # it modified
    MODIFY = 1 
    DELETE = 2

class JavaChange(NamedTuple):
    """ A change in Java source code (add/modify/remove) at a particular level
        of the hierarchy.
    """
    identifier: JavaIdentifier
    change_type: ChangeType

def test_pos_to_java_unit_matcher():
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

    finder = PosToJavaUnitMatcher(tree)
    assert [h.name for h in finder.find_range(0, 40)] == ["F", "C1", "C1M1"]
    finder = PosToJavaUnitMatcher(tree)
    assert [h.name for h in finder.find_range(0, 105)] == ["F", "C1", "C1M1", "C1M2"]
    finder = PosToJavaUnitMatcher(tree)
    assert [h.name for h in finder.find_range(0, 106)] == ["F", "C1", "C1M1", "C1M2", "C2"]
    finder = PosToJavaUnitMatcher(tree)
    assert [h.name for h in finder.find_range(0, 180)] == ["F", "C1", "C1M1", "C1M2", "C2", "C2M1", "C2M2"]