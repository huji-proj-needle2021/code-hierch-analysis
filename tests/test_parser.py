from git_analysis.java_decl_parser import JavaParser, JavaLexer
from pathlib import Path
import re

TEST_FILE_PATH = Path(__file__).parent / "test_files"


def test_java_parse_class():
    txt = """{ class Foo<T,A> implements Foo and extends bar {
        static {
            ey {} {} "{" 
            // {{
        }
        junk inbetween
        @interface Bar {
            more junk -> {} lel woot
            class Baz {
                הכל נכון גם כשיש עברית, 
                אפילו שהלקסר מתעלם ממנה כי לא אכפת לנו באמת מליטרלים
            }//ENDBAZ
        }//ENDBAR
    }//ENDFOO
    } """
    tok = list(JavaLexer().lex(txt))
    print(tok)
    parser = JavaParser()
    parser._set_tokens(tok)
    ending_token_ix, members = parser._parse_members("class", 1)
    assert len(members) == 1
    clazz = members[0]

    assert clazz and clazz.name == "Foo"
    assert clazz.members[0].name == "Bar"
    assert clazz.members[0].members[0].name == "Baz"

    assert clazz.members[0].start == txt.index("interface Bar"), "start position of Bar class"
    assert clazz.members[0].end == next(re.finditer(r"//ENDBAR", txt)).start(), "end position of Bar class"
    assert clazz.members[0].members[0].start == txt.index("class Baz"), "start position of Baz class"
    assert clazz.members[0].members[0].end == next(re.finditer(r"//ENDBAZ", txt)).start(), "end position of Baz class"
    
    assert clazz.start == txt.index("class Foo"), "beginning of Foo class"
    assert clazz.end == next(re.finditer(r"//ENDFOO", txt)).start(), "end position of Foo class"
    assert parser.tokens[ending_token_ix].value == "}"


def test_java_parse_method():
    txt = """{
        int assignment = calcSomething();
        int lambda = (a b) -> { {} {} () };
        junk inbetween etcetra {}
        @annotA
        @annoB(blah () blah {} /* blah */)
        void foo() {
           {} {} "{{{"
           /* {{ */    
        }//ENDFOO
        @noo()
        class Bar<blah> extends T<> {

        }//ENDBAR
    }"""
    tok = list(JavaLexer().lex(txt))
    parser = JavaParser()
    parser._set_tokens(tok)

    _ix, members = parser._parse_members("class", 1)
    assert members[0].name == "foo"
    assert members[0].start == txt.index("foo()"), "start position of foo method"
    assert members[0].end == next(re.finditer(r"//ENDFOO", txt)).start(), "end position of foo method"
    assert members[1].name == "Bar"
    assert members[1].start == txt.index("class Bar"), "start position of bar class"
    assert members[1].end == next(re.finditer(r"//ENDBAR", txt)).start(), "end position of bar class"

def test_java_parse_file():
    txt = """
    // blah blah
    // more blah blah about the package blah
    package com.needle.proj

    some junk etc
    import blah blah
    ;;
    class Foo {
        junk
        class FooNested {
            void FooNestedFunc() {
                {} 
            }
        }
    }
    blah blah inbetween
    class Bar {

    }
    """

    file = JavaParser().parse_java(txt)
    assert file.name == "com.needle.proj"
    assert file.members[0].name == "Foo"
    assert file.members[0].members[0].name == "FooNested"
    assert file.members[0].members[0].members[0].name == "FooNestedFunc"
    assert file.members[1].name == "Bar"

def test_f1():
    f = TEST_FILE_PATH / "AttachTryCatchVisitor.java"
    bs = f.read_bytes()
    parser = JavaParser()
    tree = parser.parse_java_bytes(bs)