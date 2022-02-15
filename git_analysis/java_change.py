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
