"""
This module is responsible for attributing changes in a git diff (a list of added/removed lines in the source code) 
to the kind of Java code that is responsible for them (a method, class or package), which we denote as "JavaHierarchy",
as they represent various hierarchies in code modularization)

Since Git has no understanding of source code, this requires us to manually parse the file changes and detect
if a line is enclosed in a method declaration, a class declaration or a package. 

We do this via Regex, which works in most cases but might have mistakes in pathological cases 
(e.g, detecting a commented method declaration below the real one)
A proper Java parsing tool would be more appropriate, but it would be more complex to integrate to the project
and possibly slower, as we only care about very few elements in the syntax tree.

"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Iterable
from enum import IntEnum
import pygit2
import re
import logging


log = logging.getLogger("java_change_detector")

@dataclass
class JavaHierarchy:
    """ A Java Hierarchy is a set of Java source code that corresponds to one or more
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
    className: Optional[str] = field(default=None)
    methodName: Optional[str] = field(default=None)


class ChangeType(IntEnum):
    ADD = 0
    MODIFY = 1
    DELETE = 2
    UNSUPPORTED = 3

    @staticmethod
    def from_delta_status_char(status: str) -> ChangeType:
        if status == "A":
            return ChangeType.ADD
        if status == "M":
            return ChangeType.MODIFY
        if status == "D":
            return ChangeType.DELETE 
        return ChangeType.UNSUPPORTED
@dataclass
class JavaChange:
    """ A change in Java source code (add/modify/remove) at a particular level
        of the hierarchy.
    """
    changed_hierarchy: JavaHierarchy
    change_type: ChangeType

# TODO: add support for tracking renames



# use binary regexes since pygit2 blobs provide binary strings
PACKAGE_RE = re.compile(rb"package\s+([^\s;]+)\s*;")

CLASS_RE = re.compile((
    r"\s*(?:(?:public|private|protected)\s+)?"  # access modifier (private/protected for inner classes)
    r"(?:static\s+\w+)?"  # for java static-nested classes
    r"class\s+(\w+)" # the class itself
    r"(?:\s+extends\s+\w+)?" # inheritance (only 1 class possible)
    r"(?:\s+implements\s+\w+(?:\s*,\s*\w+)*)?" # implements one or more interfaces, delimited by asterisks
    r"\s*{"

), re.MULTILINE)


METHOD_RE = re.compile(r"")
class JavaChangeDetector:
    """ Used to determine changes to a Java project via git """

    def identify_changes(self, repo: pygit2.Repository, patch) -> Iterable[JavaChange]:
        """ Given a git repository and patch(object that represents a difference in a file between two commits, possibly
            with renaming), determines the Java hierarchies that were changed"""
        delta = patch.delta
        hunks = patch.hunks

        change_type = ChangeType.from_delta_status_char(delta.status_char())
        if change_type == ChangeType.DELETE:
            file_containing_package = delta.old_file
        else:
            file_containing_package = delta.new_file
        
        file_contents: bytes = repo[file_containing_package.id].data
        package_match = next(PACKAGE_RE.finditer(file_contents), None)
        if not package_match:
            log.warn(f"Couldn't determine Java package for file {file_containing_package.path}")
            package = "UNKNOWN_PACKAGE"
        else:
            package = str(package_match.group(1))

        yield JavaChange(changed_hierarchy=JavaHierarchy(package=package), change_type=change_type)

        if change_type == ChangeType.DELETE:
            return

        current_class = "NO_CLASS"


        for hunk in hunks:
            print("old_lines", hunk.old_lines, "new_lines", hunk.new_lines)
            for line in hunk.lines:
                print(line.origin, line.content, end="")
