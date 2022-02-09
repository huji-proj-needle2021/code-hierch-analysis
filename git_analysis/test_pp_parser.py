from __future__ import annotations
from typing import Union
from logging import basicConfig
import pyparsing as pp
# pp.ParserElement.enable_packrat()

from typing import List, NamedTuple, Optional

class Method(NamedTuple):
    name: str
    start: int
    end: int

class Class(NamedTuple):
    name: str
    start: int
    end: int
    members: List[Union[Class, Method]]

class JavaFile(NamedTuple):
    start: int
    classes: List[Class]
    package_name: Optional[str] = None

# definition of grammar

single_line_comment = pp.Literal("//") + ... + pp.line_end
multiline_comment = pp.Literal("/*") + ... + pp.Literal("*/")

SEMICOLON = pp.Literal(";").suppress()
LBRACE, RBRACE = map(pp.Suppress, map(pp.Literal, ["{", "}"]))
LPAREN, RPAREN = map(pp.Suppress, map(pp.Literal, ["(", ")"]))

identifier = pp.Word(pp.alphas+"_$", pp.alphanums+"_$")
comment = (single_line_comment | multiline_comment).suppress()

# we don't really care about modifiers, but putting them might
# make parsing faster
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
    "strictfp",
    "default" # default interface method
], as_keyword=True)


# types

# generic, array, namespaced, etc...
opt_type_parameters = pp.Opt(pp.nested_expr("<", ">"))

inner_type = pp.delimited_list(identifier + opt_type_parameters, ".", min=1)
type_ = (inner_type + (pp.Literal("[") + pp.Literal("]"))[...]).suppress()

# method

# we don't care about a method's body, but need to deal with the fact it might
# have even more nested brackets
method_body = pp.nested_expr("{", "}").suppress()

parameter_list = LPAREN + ... + RPAREN
opt_throws = pp.Opt(pp.Keyword("throws") + pp.SkipTo(method_body | SEMICOLON)).suppress()
ctor = identifier("name") + parameter_list + opt_throws + method_body

# an interface method may end with a semicolon rather than a block
method_declaration = type_ + identifier("name") + parameter_list + opt_throws + (method_body | SEMICOLON)
ctor_or_method_declaration = pp.Located(modifier[...] + opt_type_parameters + (ctor | method_declaration))

def method_parse_action(res: pp.ParseResults) -> Method:
    return Method(
        start=res["locn_start"],
        end=res["locn_end"],
        name=res["value"]["name"]
    )
ctor_or_method_declaration.set_parse_action(method_parse_action)
ctor_or_method_declaration.ignore(comment)


# class/interface/enum class/annotation etc..

class_declaration = pp.Forward()
class_member = pp.Forward()

class_member <<= class_declaration | ctor_or_method_declaration

class_body = LBRACE + pp.Group(class_member[...])("classes") + RBRACE
# opt_extends = pp.Opt(pp.Keyword("extends") + pp.delimited_list(type_, delim=",", combine=True)).suppress()
# opt_implements = pp.Opt(pp.Keyword("implements") + pp.delimited_list(type_, delim=",", combine=True)).suppress()
class_declaration <<= pp.Located(modifier[...] + pp.one_of(["enum", "class", "interface", "@interface"],
                               as_keyword=True) + identifier("name") + ... + class_body)


def class_declaration_parse_action(res: pp.ParseResults) -> Class:
    value = res["value"]
    return Class(
        name=value["name"],
        start=res["locn_start"],
        end=res["locn_end"],
        members=[v for v in value["classes"] if isinstance(v, Class) or isinstance(v, Method)]
    )
class_declaration.set_parse_action(class_declaration_parse_action)
class_declaration.ignore(comment)

# entire file

package = pp.Keyword("package") + pp.delimited_list(identifier, ".", combine=True) + SEMICOLON
package.ignore(comment)


def test_pp_type():
    types = [
        "Foo",
        "T[]",
        "ArrayList<Foo>[][]",
        "ArrayList<ArrayList<T>[][]>[][][]"
    ]
    for t in types:
        type_.parse_string(t, parse_all=True)

def test_pp_method_parse():
    some_method = """static <T wat> Map<Wow, T[][]> theFunction(i don't care...) throws something { 
        don't care about what's inside at all
        even if there are more brackets inside {}
        or quoted brackets which we don't care about either: "{}" "{
        }"
        }"""
    method_obj = ctor_or_method_declaration.parse_string(some_method, parse_all=True)[0]
    assert method_obj.name == "theFunction"

    ctor = "public Main() {}"
    ctor_obj = ctor_or_method_declaration.parse_string(ctor, parse_all=True)[0]
    assert ctor_obj.name == "Main"

def test_pp_lone_class():
    raw = """
    class Class {
        int foo() {

        }
    }
    """

    res = class_declaration.parse_string(raw, parse_all=True)[0]
    assert res.name == "Class"

def test_pp_generic_lone_class():
    raw = """
    class Class<T> implements Foo<T> {
        int foo() {

        }
    }
    """

    res = class_declaration.parse_string(raw, parse_all=True)[0]
    assert res.name == "Class"

def test_pp_single_nested_class():
    raw = """
    class Class {
        class Inner {
            void foo() {

            }
        }
    }
    """

    res: Class = class_declaration.parse_string(raw, parse_all=True)[0]
    assert res.name == "Class"
    assert res.members[0].name == "Inner"
    assert res.members[0].members[0].name == "foo"


def test_pp_multiple_nested_classes():
    raw = """
    class Class {
        class Inner {
            void foo() {

            }
        }
        class SecondInner {
            int bar() {}
        }
        void aMethod() {

        }
        class AnotherClass {

        }
    }
    """

    res: Class = class_declaration.parse_string(raw, parse_all=True)[0]
    assert res.name == "Class"
    assert res.members[0].name == "Inner"
    assert res.members[0].members[0].name == "foo"
    assert res.members[1].name == "SecondInner"
    assert res.members[1].members[0].name == "bar"
    assert res.members[2].name == "aMethod"
    assert res.members[3].name == "AnotherClass"
    
def test_pp_class_with_unrecognized_elements():
    raw = """
    class Class {
        int notInMyGrammar = doo();
        @Override // nor is this one
        void foo() {}
    }
    """

    res: Class = class_declaration.parse_string(raw, parse_all=True)[0]
    assert res.name == "Class"
    assert res.members[0].name == "foo"