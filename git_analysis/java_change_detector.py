from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
from enum import IntEnum, auto
import pygit2
import re
import logging


log = logging.getLogger("java_change_detector")

@dataclass
class JavaHierarchy:
    """ A hierarchy in a program that has changed (e.g, a program module, file, function, etc..)
        In Java we define 3 hierarchies:

        - Java Package (corresponds to a module)
        - Java Class (in Java, this usually corresponds to a file)
        - Java Method/Function (we make no distinction between static and non-static methods)

        A change in a java method implies a change in the class it belongs to
        Likewise, a change in a class implies a change in a package.

        We make no distinction between adding, modifying or removing any of these hierachies.
        TODO: add support for renaming (track renames of functions)
    """
    package: str
    className: Optional[str] = field(default=None)
    methodName: Optional[str] = field(default=None)


@dataclass
class JavaChange:
    """ A change in Java source code (add/modify/remove) """
    changed_hierarchy: JavaHierarchy

# TODO: add support for tracking renames


PACKAGE_RE = re.compile(rb"package\s+([^\s;]+)\s*;")

class JavaChangeDetector:
    """ Used to determine changes to a Java project via git """

    def identify_changes(self, repo: pygit2.Repository, patch) -> List[JavaChange]:
        """ Given a git repository and patch(object that represents a difference in a file between two commits, possibly
            with renaming), determines the Java hierarchies that were changed"""
        delta = patch.delta
        hunks = patch.hunks

        hunks = []
        new_file: bytes = repo[delta.new_file.id].data
        package = next(PACKAGE_RE.finditer(new_file), None)
        if not package:
            log.warn(f"Couldn't determine Java package for file {delta.new_file.path}")
            package = "UNKNOWN_PACKAGE"
        else:
            package = package.group(1)

        return [JavaChange(changed_hierarchy=JavaHierarchy(package=package))]

        for hunk in hunks:
            hunk_object = { "lines": []}
            hunks.append(hunk_object)
            for line in hunk.lines:
                hunk_object["lines"].append({
                    "content": line.content
                })
        
        return []
