""" In this module we define a minimal Java syntax tree that contains packages, 
    classes and methods, and implement a basic parser for that structure using
    Regex. 

    We chose Regexes over a proper Java parser due to speed: We are going to scan hundreds-thousands
    of commits, each with several files that have to be parsed. Using a full blown parser would be slow
    and redundant as we don't care about most of Java's syntactic elements.

    Since a Regex cannot deal with recursive structures, this has some drawbacks to the accuracy of the
    output tree - it will be mistaken when finding out declarations inside comments, or dealing with Java inner
    classes.

"""
from __future__ import annotations
from .java_change import JavaIdentifier, JavaChange, ChangeType
from typing import NamedTuple, Iterable, List
import logging
import re
from .utils import iterate_regex_matches_sequentially
import pyparsing as pp

log = logging.getLogger("java_parser")

class JavaMethod(NamedTuple):
    name: str
    definition_byte_pos: int
    clazz: JavaClass

    def to_change(self, change_type: ChangeType) -> JavaChange:
        return JavaChange(changed_hierarchy=JavaIdentifier(
            package=self.clazz.file.package,
            class_name=self.clazz.name,
            method_name=self.name
        ), change_type=change_type)

class JavaClass(NamedTuple):
    name: str
    definition_byte_pos: int
    methods: List[JavaMethod]
    file: JavaFile

    def to_changes(self, change_type: ChangeType) -> Iterable[JavaChange]:
        if len(self.methods) == 0:
            yield JavaChange(changed_hierarchy=JavaIdentifier(
                package=self.file.package,
                class_name=self.name
            ), change_type=change_type)
        for method in self.methods:
            yield method.to_change(change_type)

class JavaFile(NamedTuple):
    package: str
    package_definition_pos: int
    classes: List[JavaClass]

    def to_changes(self, change_type: ChangeType) -> Iterable[JavaChange]:
        if len(self.classes) == 0:
            yield JavaChange(changed_hierarchy=JavaIdentifier(
                package=self.package
            ), change_type=change_type)
        for clazz in self.classes:
            yield from clazz.to_changes(change_type)


PACKAGE_RE = re.compile(r"\bpackage\s+([^\s;]+)\s*;")
PACKAGE_RE_B = re.compile(bytes(PACKAGE_RE.pattern, 'utf-8'), re.MULTILINE)

CLASS_RE = re.compile((
    r"(?:\b(?:public|private|protected)\s+)?"  # access modifier (private/protected for inner classes)
    r"(?:\bstatic\s+\w+)?"  # for java static-nested classes
    r"\bclass\s+(\w+)" # the class itself
    r"(?:\s+extends\s+\w+)?" # inheritance (only 1 class possible)
    r"(?:\s+implements\s+\w+(?:\s*,\s*\w+)*)?" # implements one or more interfaces, delimited by asterisks
    r"\s*{"
), re.MULTILINE)
CLASS_RE_B = re.compile(bytes(CLASS_RE.pattern, 'utf-8'), re.MULTILINE)

METHOD_RE = re.compile((
    r"(?:\b(?:public|private|protected)\s+)?"  # access modifier
    r"(?:\bstatic\s+\w+)?"  # static method
    r"\b\w+\s+" # the return type
    r"(\w+)\s*" # the function name
    r"\([^)]*\)" # argument list 
    r"\s*{"
), re.MULTILINE)
METHOD_RE_B = re.compile(bytes(METHOD_RE.pattern, 'utf-8'), re.MULTILINE)

def parse_java_file(contents: bytes, path: str) -> JavaFile:
    log.debug(f"parsing java file at {path}")

    package_match = next(PACKAGE_RE_B.finditer(contents), None)
    class_match_it = CLASS_RE_B.finditer(contents)
    method_match_it = METHOD_RE_B.finditer(contents)

    if package_match is None:
        inferred_package = path.replace("/src/main/", "/")
        log.warn(
            f"No Java package definition found, using inferred name {inferred_package}")
        current_package = JavaFile(
            package=inferred_package, package_definition_pos=0, classes=[])
    else:
        current_package = JavaFile(package=str(package_match.group(
            1)), package_definition_pos=package_match.start(0), classes=[])

    current_class = None
    for it_index, match in iterate_regex_matches_sequentially([class_match_it, method_match_it]):
        if it_index == 0:
            current_package.classes.append(JavaClass(name=str(match.group(1)), definition_byte_pos=match.start(0), methods=[],
                                                        file=current_package))
            current_class = current_package.classes[-1]
        elif it_index == 1:
            if current_class is None:
                log.error(
                    f"Java method {match.group(1)} has no class definition preceeding it, skipping!")
                continue
            current_class.methods.append(JavaMethod(name=str(match.group(
                1)), definition_byte_pos=match.start(0), clazz=current_class))
        else:
            raise ValueError("Impossible")
    
    return current_package



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

# definition of grammar

single_line_comment = pp.Literal("//") + ... + pp.line_end
multiline_comment = pp.Literal("/*") + ... + pp.Literal("*/")

SEMICOLON = pp.Literal(";").suppress()
LBRACE, RBRACE = map(pp.Suppress, map(pp.Literal, ["{", "}"]))
LPAREN, RPAREN = map(pp.Suppress, map(pp.Literal, ["(", ")"]))

identifier = pp.Word(pp.alphas+"_", pp.alphanums+"_")
comment = (single_line_comment | multiline_comment).suppress()
package = pp.Keyword("package") + pp.delimited_list(identifier, ".", combine=True) + SEMICOLON

modifier = pp.one_of([
    "Annotation",
    "public",
    "protected",
    "private",
    "static" ,
    "abstract",
    "final",
    "native",
    "synchronized",
    "transient",
    "volatile",
    "strictfp"
], as_keyword=True)

# we don't care about a method's block, but need to deal with the fact it might
# have even more nested brackets
block = pp.nested_expr("{", "}")

#   { junk {} }

class_body = pp.Forward()
enum_declaration = pp.Keyword("enum") + identifier  + ... + RBRACE
normal_class_declaration = pp.Keyword("class") + identifier + ... + LBRACE + class_body  + RBRACE
interface_declaration = (pp.Literal("@") + pp.Literal("interface")) | pp.Keyword("interface") + identifier + ... + RBRACE
class_declaration = normal_class_declaration | enum_declaration
class_or_interface_declaration = modifier[...] + (class_declaration | interface_declaration)
compilation_unit = pp.Opt(package) + ... + class_or_interface_declaration[...]

# one identifier: ctor
# two identifiers: return type followed by method name
method_declaration = (modifier[...] + identifier[1,2] + LPAREN + ... + RPAREN + block)

member_declaration = class_declaration | interface_declaration | method_declaration
class_body_declaration_inner= (
    (pp.Keyword("static") + block) | (modifier[...] + member_declaration) | SEMICOLON)

class_body_declaration_inner= modifier[...] + member_declaration 

# there are probably other elements inside a class or even variations we missed,
# we just ignore them
class_body_declaration = pp.SkipTo(class_body_declaration_inner) + class_body_declaration_inner

class_body <<= class_body_declaration[...]

def test_pp_block():
    single_block = "{}"
    nested_block = "{{}}"
    single_block_with_junk = "{junk etc}"
    nested_blocks_with_junk = "{junk { even more } and more {} do { blah blah }}"
    block.parse_string(single_block, parse_all=True)
    block.parse_string(nested_block, parse_all=True)
    block.parse_string(single_block_with_junk, parse_all=True)
    block.parse_string(nested_blocks_with_junk, parse_all=True)

def test_pp_method_parse():
    some_method = """static public retType theFunction(i don't care...) { 
        don't care about what's inside at all
        even if there are more brackets inside {}
        or quoted brackets which we don't care about either: "{}" "{

        }"
        }"""
    method_declaration.parse_string(some_method, parse_all=True)

    ctor = "public Main() {}"
    method_declaration.parse_string(ctor, parse_all=True)
    
def test_pp_class_parse():
    basic_class = """class MyClass implements some junk and stuff {
        void myFunction(){

        }
        other junk inside will be ignored

        @or this
        class InnerClass {
            static class AnotherInnerClass I don't even know if it compiles {
                ;

            }
        }
        ;
        class AnotherInnerClass 
        { }
    }"""

    basic_class = """class MyClass implements some junk and watnot {
        {}
        junk 
        ;{{}}
        more junk
        LikeACtor() {

        }
        {}
        even junk with braces {{}}
        static {}
        {}
        void bar() {

        }
    }"""

    res = class_declaration.parse_string(basic_class, parse_all=True)
    print(res)
    assert set(res).issuperset(["MyClass", "LikeACtor", "bar"])