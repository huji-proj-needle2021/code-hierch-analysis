""" This file defines a few types needed to represent a change in the Java source code,
    which will act as the items in the itemset algorithm
"""
from typing import NamedTuple, Optional
from enum import IntEnum

class JavaIdentifier(NamedTuple):
    """ An identifier to some unit of Java code that corresponds to one or more
        hierarchies in program modularization.
        For this project we look at 3 hierarchies:

        - Java Package
        - Java Class 
        - Java Method/Function (we make no distinction between static and non-static methods)

        More specific hierarchies belong to their outer ones - a method must have a class and and a package,
        a class must have a package.

        TODO: nested classes (multiple levels of classnames)
        TODO: break up a package into its components (e.g, com.foo.A belongs to package 'foo' belongs to package 'com')

    """
    package: str
    class_name: Optional[str] = None
    method_name: Optional[str] = None


class ChangeType(IntEnum):
    """ The kind of change reflected by a git diff line. """
    ADD = 0
    MODIFY = 1 
    DELETE = 2
    UNSUPPORTED = 3

class JavaChange(NamedTuple):
    """ A change in Java source code (add/modify/remove) at a particular level
        of the hierarchy.
    """
    changed_hierarchy: JavaIdentifier
    change_type: ChangeType