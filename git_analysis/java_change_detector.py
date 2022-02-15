"""
This module is responsible for attributing changes in a git diff (which operates on raw text, and has no understanding of the source code)
into Java code hierarchies that contain them - packages, classes and methods. This is done by parsing
the source files changed within a diff(see `java_parser` module) and matching each hunk of changed text
to the nearest Java elements that contain them, based on their byte offsets in the file.

"""
from __future__ import annotations
from typing import Any, Optional, List, Iterable, Tuple, NamedTuple, Set
import pygit2
import logging
from .java_decl_parser import JavaParser, JavaHierarchy
from .java_change import JavaChange, ChangeType, JavaIdentifier, PosToJavaUnitMatcher
import subprocess

log = logging.getLogger("java_change_detector")


class GitHunkOffsets(NamedTuple):
    """ This class contains the byte offsets of the text that was added or deleted
        in a Git diff
        
        (The pygit2 hunk object provides information about line number ranges, we
        prefer to deal with byte offset ranges since Java statements aren't necessarily
        line oriented)
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

    def display(self, old: Optional[bytes], new: Optional[bytes]) -> str:
        """ Displays the hunk(given the raw contents of the old and new files it
            was produced from) """
        st = []
        if old is not None and self.deleted_byte_range is not None:
            old_from, old_to = self.deleted_byte_range
            old_st = str(old[old_from: old_to], 'latin-1')
            st.append(f"-\t{repr(old_st)}")
        if new is not None and self.added_byte_range is not None:
            new_from, new_to = self.added_byte_range
            new_st = str(new[new_from: new_to], 'latin-1')
            st.append(f"+\t{repr(new_st)}")
        return "\n".join(st)
class JavaChangeDetector:
    """ Used to determine changes to a Java project via git """

    def __init__(self, repo: pygit2.Repository):
        self.__repo = repo
        self.__parser = JavaParser()

    def identify_changes_new_file(self, patch) -> Iterable[JavaChange]:

        new_file = patch.delta.new_file
        new_file_contents: bytes = self.__repo[new_file.id].data

        log.debug(f"Identifying changes in a new file {new_file.path}")

        hierarchy = self.__parser.parse_java_bytes(new_file_contents)
        for hierch in hierarchy.iterate_dfs_preorder():
            yield JavaChange(identifier=JavaIdentifier(hierch), change_type=ChangeType.ADD)

    def identify_changes_deleted_file(self, patch) -> Iterable[JavaChange]:
        deleted_file = patch.delta.old_file
        deleted_file_contents: bytes = self.__repo[deleted_file.id].data
        
        log.debug(f"Identifying changes in a deleted file {deleted_file.path}")

        hierarchy = self.__parser.parse_java_bytes(deleted_file_contents)
        for hierch in hierarchy.iterate_dfs_preorder():
            yield JavaChange(identifier=JavaIdentifier(hierch), change_type=ChangeType.DELETE)

    def identify_changes_modified_file(self, patch) -> Iterable[JavaChange]:
        old_file = patch.delta.old_file
        new_file = patch.delta.new_file
        old_content: bytes = self.__repo[old_file.id].data
        new_content: bytes = self.__repo[new_file.id].data

        log.debug(f"Identifying changes in a modified file {old_file.path}")
        old_hierch = self.__parser.parse_java_bytes(old_content)
        new_hierch = self.__parser.parse_java_bytes(new_content)
        old_hierch_matcher = PosToJavaUnitMatcher(old_hierch)
        new_hierch_matcher = PosToJavaUnitMatcher(new_hierch)
        deletes: Set[JavaIdentifier] = set()
        adds: Set[JavaIdentifier] = set()
        for hunk in patch.hunks:
            hunk_offsets = GitHunkOffsets.from_pygit_hunk(hunk)
            # print("Displaying hunk", hunk_offsets.display(old_content, new_content), sep="\n")
            if hunk_offsets.deleted_byte_range is not None:
                deletes.update(map(JavaIdentifier, old_hierch_matcher.find_range(
                    hunk_offsets.deleted_byte_range[0], 
                    hunk_offsets.deleted_byte_range[1]
                )))
            if hunk_offsets.added_byte_range is not None:
                adds.update(map(JavaIdentifier, new_hierch_matcher.find_range(
                    hunk_offsets.added_byte_range[0],
                    hunk_offsets.added_byte_range[1]
                )))
        updates = adds & deletes
        for add in adds:
            if add not in updates:
                yield JavaChange(identifier=add, change_type=ChangeType.ADD)
        for delete in deletes:
            if delete not in updates:
                yield JavaChange(identifier=delete, change_type=ChangeType.DELETE)
        for update in updates:
                yield JavaChange(identifier=update, change_type=ChangeType.MODIFY)

    def identify_changes(self, patch) -> Iterable[JavaChange]:
        """ Given a git repository and patch(object that represents a difference in a file between two commits, possibly
            with renaming), determines the Java hierarchies that were changed"""
        delta = patch.delta

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
