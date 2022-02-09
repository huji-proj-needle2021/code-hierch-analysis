from __future__ import annotations
from logging import basicConfig
import pyparsing as pp
from typing import List, NamedTuple, Optional

class Method(NamedTuple):
    name: str
    start: int
    end: int

class Class(NamedTuple):
    name: str
    start: int
    end: int
    methods: List[Method]
    classes: List[Class]

class JavaFile(NamedTuple):
    start: int
    end: int
    classes: List[Class]
    package_name: Optional[str] = None

# definition of grammar

single_line_comment = pp.Literal("//") + ... + pp.line_end
multiline_comment = pp.Literal("/*") + ... + pp.Literal("*/")

SEMICOLON = pp.Literal(";").suppress()
LBRACE, RBRACE = map(pp.Suppress, map(pp.Literal, ["{", "}"]))
LPAREN, RPAREN = map(pp.Suppress, map(pp.Literal, ["(", ")"]))

identifier = pp.Word(pp.alphas+"_", pp.alphanums+"_")
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


# method

# we don't care about a method's block, but need to deal with the fact it might
# have even more nested brackets
block = pp.nested_expr("{", "}").suppress()

# first identifier is type, second identifier is method name. first identifier is missing for
# constructor
# definition

opt_throws = pp.Opt(pp.Keyword("throws") + pp.SkipTo(block | SEMICOLON)).suppress()

ctor = identifier("name") + opt_throws + LPAREN + ... + RPAREN + block

# an interface method may end with a semicolon rather than a block
method_declaration = identifier + identifier("name") + LPAREN + ... + RPAREN + opt_throws + (block | SEMICOLON)

ctor_or_method_declaration = ctor | method_declaration

def method_parse_action(s: str, loc: int, res: pp.ParseResults) -> Method:
    return Method(
        start=loc,
        end=loc+len(s),
        name=res["name"]
    )
ctor_or_method_declaration.set_parse_action(method_parse_action)




# class/interface/enum class/annotation etc..

class_body = pp.Forward()
class_declaration = modifier[...] + pp.one_of(["enum", "class", "interface", "@interface"], as_keyword=True) + identifier("name") + ... + LBRACE + class_body("class_body") + RBRACE

class_member = pp.SkipTo(modifier[...] + (class_declaration | ctor_or_method_declaration), include=True)
# class_member = modifier[...] + (class_declaration | ctor_or_method_declaration | SEMICOLON)
# class_member = pp.SkipTo(class_member).suppress() + class_member
class_body <<= pp.Group(class_member[...])

def class_declaration_parse_action(s: str, loc: int, res: pp.ParseResults) -> Class:
    return Class(
        name=res["name"],
        start=loc,
        end=loc+len(s),
        methods=[m for m in res["class_body"] if isinstance(m, Method)],
        classes=[c for c in res["class_body"] if isinstance(c, Class)]
    )
class_declaration.set_parse_action(class_declaration_parse_action)

# entire file

package = pp.Keyword("package") + pp.delimited_list(identifier, ".", combine=True) + SEMICOLON
compilation_unit = pp.Opt(package)("package") + ... + class_declaration[...]("classes")

def compilation_unit_parse_action(s: str, loc: int, res: pp.ParseResults) -> JavaFile:
    return JavaFile(
        package_name=res["package"][1] if res["package"] else None,
        start=loc,
        end=loc+len(s),
        classes=[c for c in res["classes"] if isinstance(c, Class)]
    )
compilation_unit.add_parse_action(compilation_unit_parse_action)

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
    some_method = """retType theFunction(i don't care...) throws something { 
        don't care about what's inside at all
        even if there are more brackets inside {}
        or quoted brackets which we don't care about either: "{}" "{

        }"
        }"""
    method_obj = method_declaration.parse_string(some_method, parse_all=True)
    assert method_obj.name == "theFunction"

    ctor = "public Main() {}"
    ctor_obj = method_declaration.parse_string(ctor, parse_all=True)
    assert ctor_obj.name == "Main"
    
def test_pp_class_parse():

    empty_class = "class Foo{}"
    res: Class = class_declaration.parse_string(empty_class, parse_all=True)[0]
    assert res.name == "Foo"


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
    res: Class = class_declaration.parse_string(basic_class, parse_all=True)[0]
    assert res.name == "MyClass"
    assert res.methods[0].name == "LikeACtor"
    assert res.methods[1].name == "bar"

    nested_class = """class MyClass implements some junk and stuff {
        void myFunction(){

        }
        other junk inside will be ignored

        @or this
        class InnerClass {
            void innerClassFun() {}
        }
        
    }"""
    res: Class = class_declaration.parse_string(nested_class, parse_all=True)[0]
    assert res.name == "MyClass"
    assert res.methods[0].name == "myFunction"
    assert res.classes[0].name == "InnerClass"
    assert res.classes[0].methods[0].name == "innerClassFun"

def test_pp_compilation_unit():
    file = """
    package com.foo.bar;

    class Foo {
        void fooFunc() {}
    }
    """

    res: JavaFile = compilation_unit.parse_string(file, parse_all=True)[0]
    assert res.package_name == "com.foo.bar"
    assert res.classes[0].name == "Foo"
    assert res.classes[0].methods[0].name == "fooFunc"