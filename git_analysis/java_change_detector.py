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
import re
import logging
from .utils import iterate_regex_matches_sequentially


log = logging.getLogger("java_change_detector")

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


class JavaMethod(NamedTuple):
    method_name: str
    definition_byte_pos: int

class JavaClass(NamedTuple):
    class_name: str
    definition_byte_pos: int
    methods: List[JavaMethod]
class JavaPackage(NamedTuple):
    package: str
    definition_byte_pos: int
    classes: List[JavaClass]


class ChangeType(IntEnum):
    """ The kind of change reflected by a git diff line. """
    ADD = 0
    MODIFY = 1 
    DELETE = 2
    UNSUPPORTED = 3

@dataclass
class JavaChange:
    """ A change in Java source code (add/modify/remove) at a particular level
        of the hierarchy.
    """
    changed_hierarchy: JavaIdentifier
    change_type: ChangeType

    @staticmethod
    def from_java_package(package: JavaPackage, change_type: ChangeType) -> Iterable[JavaChange]:
        if len(package.classes) == 0:
            yield JavaChange(changed_hierarchy=JavaIdentifier(package=package.package), change_type=change_type)
        for clazz in package.classes:
            if len(clazz.methods) == 0:
                yield JavaChange(changed_hierarchy=JavaIdentifier(package=package.package, class_name=clazz.class_name), change_type=change_type)
            for method in clazz.methods:
                yield JavaChange(changed_hierarchy=JavaIdentifier(package=package.package, class_name=clazz.class_name, method_name=method.method_name),
                                 change_type=change_type)



PACKAGE_RE = re.compile(r"package\s+([^\s;]+)\s*;")
PACKAGE_RE_B = re.compile(PACKAGE_RE.pattern, re.MULTILINE)

CLASS_RE = re.compile((
    r"\s*(?:(?:public|private|protected)\s+)?"  # access modifier (private/protected for inner classes)
    r"(?:static\s+\w+)?"  # for java static-nested classes
    r"class\s+(\w+)" # the class itself
    r"(?:\s+extends\s+\w+)?" # inheritance (only 1 class possible)
    r"(?:\s+implements\s+\w+(?:\s*,\s*\w+)*)?" # implements one or more interfaces, delimited by asterisks
    r"\s*{"
), re.MULTILINE)
CLASS_RE_B = re.compile(bytes(CLASS_RE.pattern, 'utf-8'), re.MULTILINE)

METHOD_RE = re.compile((
    r"\s*(?:(?:public|private|protected)\s+)?"  # access modifier
    r"(?:static\s+\w+)?"  # static method
    r"\s*\w+\s+" # the return type
    r"(\w+)\s*" # the function name
    r"\([^)]*\)" # argument list 
    r"\s*{"
), re.MULTILINE)
METHOD_RE_B = re.compile(bytes(METHOD_RE.pattern, 'utf-8'), re.MULTILINE)

class JavaChangeDetector:
    """ Used to determine changes to a Java project via git """

    def __init__(self, repo: pygit2.Repository):
        self.__repo = repo

    def identify_changes_within_file_and_hunks(self, file_contents: bytes, changed_lines: Iterable[Any]) -> Iterable[JavaChange]:
        """ Given the contents of a file within a git diff(either the old or the new version), and
            an iterator over DiffLines that were either deleted(if this is the old file) or added(if this is the new file) """
    
        pass

    def parse_java_file(self, contents: str, path: str) -> Iterable[JavaPackage]:
        log.debug(f"parsing java file at {path}")

        package_match_it = PACKAGE_RE.finditer(contents)
        class_match_it = CLASS_RE.finditer(contents)
        method_match_it = METHOD_RE.finditer(contents)

        current_package = None
        current_class = None
        for it_index, match in iterate_regex_matches_sequentially([package_match_it, class_match_it, method_match_it]):
            # log.debug("it_index", it_index, "match", match)
            if it_index == 0:
                if current_package is not None:
                    log.warn("Found another package in the same Java file");
                    yield current_package
                current_package = JavaPackage(package=match.group(1), definition_byte_pos=match.start(0), classes=[])

            elif it_index == 1:
                if current_package is None:
                    inferred_package = path.replace("/src/main/", "/")
                    log.warn(f"Java class {match.group(1)} has no package definition preceeding it, using inferred name {inferred_package}")
                    current_package = JavaPackage(package=inferred_package, definition_byte_pos=0, classes=[])
                current_package.classes.append(JavaClass(class_name=match.group(1), definition_byte_pos=match.start(0), methods=[]))
                current_class = current_package.classes[-1]
            elif it_index == 2:
                if current_class is None:
                    log.error(f"Java method {match.group(1)} has no class definition preceeding it, skipping!")
                    return
                current_class.methods.append(JavaMethod(method_name=match.group(1), definition_byte_pos=match.start(0)))
            else:
                raise ValueError("Impossible")
        
        if current_package is not None:
            yield current_package
                    


        
    def identify_changes_new_file(self, patch) -> Iterable[JavaChange]:

        new_file = patch.delta.new_file
        new_file_contents = str(self.__repo[new_file.id].data, 'utf-8')
        
        log.debug(f"Identifying changes in an added file {new_file.path}")
        new_packages = self.parse_java_file(new_file_contents, new_file.path)
        for package in new_packages:
            yield from JavaChange.from_java_package(package, ChangeType.ADD)

    def identify_changes_deleted_file(self, patch) -> Iterable[JavaChange]:
        deleted_file = patch.delta.old_file
        deleted_file_contents = str(self.__repo[deleted_file.id].data, 'utf-8')
        
        log.debug(f"Identifying changes in a deleted file {deleted_file.path}")
        deleted_packages = self.parse_java_file(deleted_file_contents, deleted_file.path)

        for package in deleted_packages:
            yield from JavaChange.from_java_package(package, ChangeType.DELETE)

    def identify_changes_modified_file(self, patch) -> Iterable[JavaChange]:
        log.debug("Identifying changes in a modified file")
        return []

    def identify_changes(self, patch) -> Iterable[JavaChange]:
        """ Given a git repository and patch(object that represents a difference in a file between two commits, possibly
            with renaming), determines the Java hierarchies that were changed"""
        delta = patch.delta
        hunks = patch.hunks

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

        # based on the old file, find out what was deleted
        for hunk in hunks:
            print("hunk header", hunk.header)
            print("hunk old_start", hunk.old_start, "hunk new_start", hunk.new_start)
            print("old_lines", hunk.old_lines, "new_lines", hunk.new_lines)
            for line in hunk.lines:
                print(line.origin, "old_lineno", line.old_lineno, "new_lineno", line.new_lineno, "content_offset", line.content_offset, line.content, end="")
            # for line in hunk.lines:
            #     if line.origin == "-":
            #         print("deleted", line.content, end="")
            #     elif line.origin == "+":
            #         print("added", line.content, end="")
            #     else:
            #         print("unsupported origin", line.origin)



# Tests

def test_package_re():
    packages = """
    package             com.foo.bar        
    ;

    package baz;
    package 
    boo
    ;
    """

    matches = [match.group(1) for match in PACKAGE_RE.finditer(packages)]
    assert matches == [ "com.foo.bar", "baz", "boo"]


def test_class_re():
    classes = """
    public   class      ClsA {
        protected static class InnerCls extends Test implements Bar {}
        class AnotherInnerClass{}
    }
    class ClsB extends Test { protected class InnerClass implements Woot 
    {}}
    """

    matches = [match.group(1) for match in CLASS_RE.finditer(classes)]
    assert matches == [ "ClsA", "InnerCls", "AnotherInnerClass", "ClsB", "InnerClass"]

def test_method_re():
    methods = """
    public static void Main(string[] args) {
    }

    protected SomeClass myFun(){ void anotherFun(int a, SomeClass b) 
    {

    }}
    """
    matches = [match.group(1) for match in METHOD_RE.finditer(methods)]
    assert matches == [ "Main", "myFun", "anotherFun"]