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
from typing import Any, Optional, List, Iterable, Tuple, NamedTuple
from enum import IntEnum
import pygit2
import logging
from .java_parser import parse_java_file, JavaPackage, JavaClass, JavaMethod
from .java_change import JavaChange, ChangeType, JavaIdentifier


log = logging.getLogger("java_change_detector")


def java_package_to_changes(package: JavaPackage, change_type: ChangeType) -> Iterable[JavaChange]:
    if len(package.classes) == 0:
        yield JavaChange(changed_hierarchy=JavaIdentifier(package=package.name), change_type=change_type)
    for clazz in package.classes:
        if len(clazz.methods) == 0:
            yield JavaChange(changed_hierarchy=JavaIdentifier(package=package.name, class_name=clazz.name), change_type=change_type)
        for method in clazz.methods:
            yield JavaChange(changed_hierarchy=JavaIdentifier(package=package.name, class_name=clazz.name, method_name=method.name),
                                change_type=change_type)

class GitHunkOffsets(NamedTuple):
    """ This class contains the byte offsets of the text that was added or deleted
        in a Git diff
        
        (The pygit2 hunk object provides information about line number ranges, we
        prefer to deal with byte offset ranges due to our use of Regex which doesn't
        automatically associate matches with line numbers)
    """

    # (inclusive, exclusive)

    deleted_byte_range: Optional[Tuple[int, int]]
    added_byte_range: Optional[Tuple[int, int]]

    @staticmethod
    def from_pygit_hunk(hunk) -> GitHunkOffsets:
        deleted_start_pos, deleted_end_pos = -1, -1
        added_start_pos, added_end_pos = -1, -1

        for line in hunk.lines:
            line_start_pos = line.content_offset
            line_end_pos = line_start_pos + len(line.raw_content)
            if line.origin == "+":
                if added_start_pos < 0:
                    added_start_pos = line_start_pos
                added_end_pos = line_end_pos

            elif line.origin == "-":
                if deleted_start_pos < 0:
                    deleted_start_pos = line_start_pos
                deleted_end_pos = line_end_pos
        
        deleted_byte_range = (
            deleted_start_pos, deleted_end_pos) if deleted_start_pos >= 0 else None
        added_byte_range = (
            added_start_pos, added_end_pos) if added_start_pos >= 0 else None

        return GitHunkOffsets(deleted_byte_range=deleted_byte_range,
                              added_byte_range=added_byte_range)

class JavaChangeDetector:
    """ Used to determine changes to a Java project via git """

    def __init__(self, repo: pygit2.Repository):
        self.__repo = repo

    def identify_changes_new_file(self, patch) -> Iterable[JavaChange]:

        new_file = patch.delta.new_file
        new_file_contents: bytes = self.__repo[new_file.id].data
        
        log.debug(f"Identifying changes in an added file {new_file.path}")
        new_package = parse_java_file(new_file_contents, new_file.path)
        return new_package.to_changes(ChangeType.ADD)

    def identify_changes_deleted_file(self, patch) -> Iterable[JavaChange]:
        deleted_file = patch.delta.old_file
        deleted_file_contents: bytes = self.__repo[deleted_file.id].data
        
        log.debug(f"Identifying changes in a deleted file {deleted_file.path}")
        deleted_package = parse_java_file(deleted_file_contents, deleted_file.path)
        return deleted_package.to_changes(ChangeType.DELETE)

    def identify_changes_modified_file(self, patch) -> Iterable[JavaChange]:
        previous_file = patch.delta.old_file
        new_file = patch.delta.new_file
        previous_content: bytes = self.__repo[previous_file.id].data
        new_content: bytes = self.__repo[new_file.id].data

        log.debug(f"Identifying changes in a modified file {previous_file.path}")

        previous_parsed_ast = parse_java_file(previous_content, previous_file.path)
        new_parsed_ast = parse_java_file(new_content, previous_file.path)

        cur_old_package = previous_parsed_ast
        cur_new_package = new_parsed_ast
        cur_old_class, cur_old_method = None, None
        cur_new_class, cur_new_method = None, None
        for hunk in patch.hunks:
            hunk_offsets = GitHunkOffsets.from_pygit_hunk(hunk)
            if hunk_offsets.deleted_byte_range is not None:
                # in the old AST, find out the java identifiers contained in the given offset
                pass
            if hunk_offsets.added_byte_range is not None:
                pass

        return []

    def identify_changes(self, patch) -> Iterable[JavaChange]:
        """ Given a git repository and patch(object that represents a difference in a file between two commits, possibly
            with renaming), determines the Java hierarchies that were changed"""
        delta = patch.delta
        
        for hunk in patch.hunks:
            print("hunk", hunk.header, "old start", hunk.old_start, "new start", hunk.new_start)
            for line in hunk.lines:
                print("\t", line.origin, line.raw_content, "content-offset:", line.content_offset)


        status_char = delta.status_char()
        if status_char == "A":
            return self.identify_changes_new_file(patch)
        elif status_char == "D":
            return self.identify_changes_deleted_file(patch)
        elif status_char == "M":
            return self.identify_changes_modified_file(patch)
        else:
            log.warning(f"Unsupported git delta status character '{status_char}', skipping")
            return []
        return []
