# %%

from contextlib import suppress
from enum import IntEnum
from lark.lark import Lark
from lark.lexer import Lexer, LexerState, Token, BasicLexer, UnexpectedCharacters, UnexpectedToken
from lark.common import LexerConf
from typing import Any, Iterator
from pathlib import Path
import re

# old_lex = BasicLexer.lex
# def overriden_lex(self, state: LexerState, parser_state: Any):
#     with suppress(UnexpectedCharacters):
#         yield from old_lex(self, state, parser_state)

# BasicLexer.lex = overriden_lex


# %%

KEYWORDS = re.findall("\S+", """
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

OPERATORS = re.findall("\S+", """
=   >   <   !   ~   ?   :   ->
==  >=  <=  !=  &&  ||  ++  --
+   -   *   /   &   |   ^   %   <<   >>   >>>
+=  -=  *=  /=  &=  |=  ^=  %=  <<=  >>=  >>>=
""")

SEPARATORS = re.findall("\S+", """"
(   )   {   }   [   ]   ;   ,   .   ...   @   ::
""")

TERMINALS_OF_INTEREST = {
    "COMMENT": r"//[^\n]*",
    "MULTILINE_COMMENT": r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/",
    "WHITESPACE": r"\s+",
    "CHAR_LIT": r"'(?:[^'\\]|\\.)*'",
    "STRING_LIT": r'"(?:[^"\\]|\\.)*"',
    "OPERATOR": rf'\b(?:{"|".join(OPERATORS)})\b',
    "SEPARATOR": rf'\b(?:{"|".join(SEPARATORS)})\b',
    "KEYWORD": rf'\b(?:{"|".join(KEYWORDS)})\b',
    "IDENTIFIER": r"\b[A-Za-z_$][A-Za-z_$0-9]*\b", 
}

# These won't be passed to Lark at all
IGNORED_TERMINALS = ["COMMENT", "MULTILINE_COMMENT", "WHITESPACE", "CHAR_LIT", "STRING_LIT"]

assert set(IGNORED_TERMINALS).issubset(TERMINALS_OF_INTEREST.keys())

class MyLexer(Lexer):
    def __init__(self, conf: LexerConf):
        regexes = []
        for group, regex in TERMINALS_OF_INTEREST.items():
            regexes.append(rf"(?P<{group}>{regex})")
        self.regex = re.compile("|".join(regexes))

    def lex(self, lexer_state: LexerState, parser_state: Any = None) -> Iterator[Token]:
        txt = lexer_state.text if isinstance(lexer_state, LexerState) else lexer_state
        for match in self.regex.finditer(txt):
            group = match.lastgroup
            if group in IGNORED_TERMINALS:
                continue
            value = match.group(group)
            yield Token(group, value, start_pos=match.start())




gramamr_file = Path(__file__).parent / "grammar.lark"
grammar = gramamr_file.read_text()
block_parser = Lark(grammar, parser="lalr", lexer=MyLexer)


txt = """
public static class Foo {
}
"""



# tree
# list(block_parser.lex(txt))
# l = MyLexer(None)
# ls = LexerState(txt)
# list(l.lex(ls, None))
print("Tokens\n",list(block_parser.lex(txt)))
tree = block_parser.parse(txt)
print(tree.pretty())
