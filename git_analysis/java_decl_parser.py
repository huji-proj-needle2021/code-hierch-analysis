""" In this module we implement a parser for Java class/interface/enum and method declarations,
    using Regex to identify interesting elements, along with bracket counting in order to determine the hierarchy
"""
import re
from enum import IntEnum, auto
from typing import Iterable, Iterator, NamedTuple, List, Optional, Tuple, Union
from .java_type import JavaClass, JavaMethod
import logging

log = logging.getLogger("java_decl_parser")

# The following definitions are based on
# https://docs.oracle.com/javase/specs/jls/se17/html/jls-3.html


KEYWORDS = re.findall(r"\S+", """
abstract   continue   for          new         switch
assert     default    if           package     synchronized
boolean    do         goto         private     this
break      double     implements   protected   throw
byte       else       import       public      throws
case       enum       instanceof   return      transient
catch      extends    int          short       try
char       final      interface    static      void
class      finally    long         strictfp    volatile
const      float      native       super       while
_
""")

# Note: most of the operators were deleted since we don't care about them
OPERATORS = re.findall(r"\S+", """
=   >   <   !   ~   ?   :   ->
""")

SEPARATORS = re.findall(r"\S+", """"
(   )   {   }   [   ]   ;   ,   .   ...   @   ::
""")

OPENING_TO_CLOSING_SEP = {
    "(": ")",
    "{": "}",
    "[": "]"
}

class TokenType(IntEnum):
    """ Based on https://docs.oracle.com/javase/specs/jls/se17/html/jls-3.html#jls-3.5 """
    IDENTIFIER = auto()
    KEYWORD = auto()
    LITERAL = auto()
    SEPARATOR = auto()
    OPERATOR = auto()


st_token_type_to_int = {
    f"g{int(variant)}": variant for variant in TokenType
}

class Token(NamedTuple):
    type: TokenType
    value: str
    pos: int

# Comments and whitespace are completley ignored
IGNORED = [
    r"//[^\n]*",
    r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/",
    r"\s+"
]

CHAR_LITERAL = r"'(?:[^'\\]|\\.)*'"
STRING_LITERAL = r'"(?:[^"\\]|\\.)*"'

# Contains a few tokens of interest - not exhaustive. Mostly used to avoid accidentally
# capturing elements we care about(like class keywords) used in other contexts(e.g, a literal)
TERMINALS_OF_INTEREST = {
    TokenType.LITERAL: "|".join([CHAR_LITERAL, STRING_LITERAL]),
    TokenType.KEYWORD: rf'\b(?:{"|".join(re.escape(kw) for kw in KEYWORDS)})\b',
    TokenType.OPERATOR: rf'(?:{"|".join(re.escape(op) for op in OPERATORS)})',
    TokenType.SEPARATOR: rf'(?:{"|".join(re.escape(sep) for sep in SEPARATORS)})',
    TokenType.IDENTIFIER: r"\b[A-Za-z_$][A-Za-z_$0-9]*\b",
}

assert set(TERMINALS_OF_INTEREST.keys()) == set(list(TokenType))

class JavaLexer():
    def __init__(self):
        regexes = []
        for group, regex in TERMINALS_OF_INTEREST.items():
            regexes.append(rf"(?P<g{group}>{regex})")
        ignored_regex = "|".join(IGNORED)
        regexes.append(rf"(?P<ignored>{ignored_regex})")
        self.regex = re.compile("|".join(regexes))

    def lex(self, text: str) -> Iterator[Token]:
        for match in self.regex.finditer(text):
            group = match.lastgroup
            if group == "ignored":
                continue
            token_type = st_token_type_to_int[group]
            value = match.group(group)
            yield Token(token_type, value, pos=match.start())


class BracketStackElement(NamedTuple):
    opener: str
    start_pos: int


CLASS_KEYWORDS = set(["class", "interface", "enum"])

class JavaParser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.main_pos = 0

    def token_at(self, pos: int) -> Optional[Token]:
        if pos >= len(self.tokens) or pos < 0:
            return None
        return self.tokens[pos]

    def parse(self) -> Iterable[JavaClass]:
        """ Begins parsing the top-level classes/interfaces/enums of a Java file"""
        i = 0
        while i < len(self.tokens):
            token = self.tokens[i]
            if token.type == TokenType.KEYWORD and token.value in CLASS_KEYWORDS:
                clazz = self.try_parse_class(i)
                if clazz is not None:
                    yield clazz
                    i = clazz.end
                else:
                    i += 1

    def try_parse_class(self, pos: int) -> Optional[JavaClass]:
        """ Tries to parse a class/interface/enum, whose keyword appears at the given position. 
        """
        if pos - 1 > 0 and self.tokens[pos - 1].value == ".":
            # we matched ".class", skip
            return None
        if self.tokens[pos + 1].type != TokenType.IDENTIFIER:
            log.warning(f"Expected to see an identifier after class/interface keyword")
            return None
        class_type = self.tokens[pos].value
        name = self.tokens[pos + 1].value
        log.debug(f"Parsing class of type {class_type}, name: {name}")
        # TODO: find an earlier beginning (modifiers belonging to class)

        # finding the opening semicolon - there may be generic or extends/implements inbetween
        brack_ix = next((i for i in range(pos + 2, len(
            self.tokens)) if self.tokens[i].value == "{"), None)
        if brack_ix is None:
            log.warning(f"Couldn't find opening bracket or semicolon for suspected class at {pos}")
            return None
        end_ix, members = self.parse_members(brack_ix + 1)

        class_keyword_pos = self.tokens[pos].pos
        end_brack_pos = self.tokens[end_ix].pos if end_ix >= 0 else self.tokens[-1].pos
        return JavaClass(start=class_keyword_pos, end=end_brack_pos + 1, name=name, kind=class_type, members=members)
    

    def try_parse_method(self, param_op_pos: int, lower_bound: int=0) -> Tuple[int, Optional[JavaMethod]]:
        """ Tries to parse a method/ctor when given a parameter list. A lower index bound specifiying the
            end of the previous member(or start of the member block) is given to prevent unnecessary backtracking.
            
            The method returns the highest index which was scanned, in either case of failure or success - this allows
            the parser to continue 
            
            In contrast to parsing a class, this method is a bit inefficient due to use of backtracking, consider the following case:
            pkg.foo.bar.ClsA.ClsB foo(); // abstract or interface method that returns ClsB
            in contrast to a method call
            int k = pkg.foo.bar.ClsA.ClsB.foo();
            or even a lambda
            var lambdaDef = (int a, int b) -> {};
        """
        return param_op_pos + 1, None

    def parse_members(self, pos_after_brack: int) -> Tuple[int, List[Union[JavaClass, JavaMethod]]]:
        """ Parses a list of method/class declarations in a block starting at given index.
            Returns the index of the closing bracket tupled with a list of parsed members, or -1 as index
            if no closing bracket was found.
        """
        members: List[Union[JavaClass, JavaMethod]] = []
        i = pos_after_brack
        while i < len(self.tokens):
            token = self.tokens[i]
            # reached end of current member block
            if token.type == TokenType.SEPARATOR and token.value == "}":
                return i, members
            # We almost definitely have a class
            if token.type == TokenType.KEYWORD and token.value in CLASS_KEYWORDS:
                clazz = self.try_parse_class(i)
                if clazz is not None:
                    members.append(clazz)
                    i = clazz.end
            # We suspect a function call (based on parameter list)
            elif token.type == TokenType.SEPARATOR and token.value == "(":
                i, method = self.try_parse_method(i)
                if method is not None:
                    members.append(method)
            
            # We found a block that doesn't belong to a class or method(e.g, a static block or
            # a lambda function declaration), skip to the block's ending.
            elif token.type == TokenType.SEPARATOR and token.value == "{":
                closing_pos = self.find_closing_bracket(i)
                i = closing_pos + 1 if closing_pos is not None else i + 1
            else:
                i += 1

        log.warning("Couldn't find ending bracket for member block, assuming end of text to be class ending")
        return -1, members


    def find_closing_bracket(self, starting_bracket_pos: int) -> Optional[int]:
        """ Given the position of a starting paren/bracket, finds the index of the corresponding ending
            bracket. If dir=1, then it scans forward, if -1, then backward. Returns None
            if no closing bracket is found. """
        assert (self.tokens[starting_bracket_pos].value in OPENING_TO_CLOSING_SEP.keys())
        starter = self.tokens[starting_bracket_pos].value
        closer = OPENING_TO_CLOSING_SEP[starter]

        n_nested_openers = 1
        for i in range(starting_bracket_pos + 1, len(self.tokens)):
            token = self.tokens[i]
            if token.value == starter:
                n_nested_openers += 1
            elif token.value == closer:
                n_nested_openers -= 1
                if n_nested_openers == 0:
                    return i
        log.warning(f"Found un-matched paren/bracket starting at position {starting_bracket_pos}, number of nested openers: {n_nested_openers}")
        return None


def test_java_parse_class():
    txt = """class Foo<T,A> implements Foo and extends bar {
        static {
            ey {} {} "{" 
            // {{
        }
        junk inbetween
        @interface Bar {
            more junk -> {} lel woot
            class Baz {

            }//ENDBAZ
        }//ENDBAR
    }"""
    tok = list(JavaLexer().lex(txt))
    print(tok)
    parser = JavaParser(tok)
    clazz = parser.try_parse_class(0)

    assert clazz and clazz.name == "Foo"
    assert clazz.members[0].name == "Bar"
    assert clazz.members[0].members[0].name == "Baz"

    assert clazz.members[0].start == txt.index("interface Bar"), "start position of Bar class"
    assert clazz.members[0].end == next(re.finditer(r"//ENDBAR", txt)).start(), "end position of Bar class"
    assert clazz.members[0].members[0].start == txt.index("class Baz"), "start position of Baz class"
    assert clazz.members[0].members[0].end == next(re.finditer(r"//ENDBAZ", txt)).start(), "end position of Baz class"
    
    assert clazz.start == 0 , "beginning of Foo class"
    assert clazz.end == len(txt), "end position of Foo class"