""" In this module we implement a parser for Java class/interface/enum and method declarations,
    using Regex to identify interesting elements, along with bracket counting in order to determine the hierarchy
"""
# %%
import re
from enum import IntEnum, auto
from typing import Iterator, NamedTuple, List


# Taken from 
KEYWORDS = re.findall("\w+", """
abstract 	continue 	for 	new 	switch
assert 	default 	goto 	package 	synchronized
boolean 	do 	if 	private 	this
break 	double 	implements 	protected 	throw
byte 	else 	import 	public 	throws
case 	enum 	instanceof 	return 	transient
catch 	extends 	int 	short 	try
char 	final 	interface 	static 	void
class 	finally 	long 	strictfp 	volatile
const 	float 	native 	super 	while
""")

class TokenType(IntEnum):
    COMMENT = auto()
    MULTILINE_COMMENT = auto()
    WHITESPACE = auto()
    CHAR_LIT = auto()
    STRING_LIT = auto()
    LBRACK = auto()
    RBRACK = auto()
    LPAR = auto()
    RPAR = auto()
    SEMICOLON = auto()
    LANG = auto()
    RANG = auto()
    ASTERISK = auto()
    KEYWORD = auto()
    IDENT = auto()
    EQ = auto()
    LAMBDA = auto()

st_token_type_to_int = {
    f"g{int(variant)}": variant for variant in TokenType
}

class Token(NamedTuple):
    type: TokenType
    value: str
    pos: int

TERMINALS_OF_INTEREST = {
    TokenType.COMMENT: r"//[^\n]*",
    TokenType.MULTILINE_COMMENT: r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/",
    TokenType.WHITESPACE: r"\s+",
    TokenType.CHAR_LIT: r"'(?:[^'\\]|\\.)*'",
    TokenType.STRING_LIT: r'"(?:[^"\\]|\\.)*"',
    TokenType.LBRACK: r"{", 
    TokenType.RBRACK: r"}",
    TokenType.LPAR: r"\(", 
    TokenType.RPAR: r"\)",
    TokenType.SEMICOLON: r";",
    TokenType.LANG: r"<", 
    TokenType.RANG: r">",
    TokenType.ASTERISK: ",",
    TokenType.KEYWORD: rf'\b(?:{"|".join(KEYWORDS)})\b',
    TokenType.IDENT: r"\b[A-Za-z_$][A-Za-z_$0-9.]*\b", # allow dots in identifiers(qualified identifiers)
    TokenType.EQ: "=",
    TokenType.LAMBDA: "->"
}

IGNORED_TERMINALS = [
    TokenType.COMMENT, TokenType.MULTILINE_COMMENT, TokenType.WHITESPACE,
    TokenType.CHAR_LIT, TokenType.STRING_LIT
]

assert set(IGNORED_TERMINALS).issubset(TERMINALS_OF_INTEREST.keys())

assert set(TERMINALS_OF_INTEREST.keys()) == set(list(TokenType))

class JavaLexer():
    def __init__(self):
        regexes = []
        for group, regex in TERMINALS_OF_INTEREST.items():
            regexes.append(rf"(?P<g{group}>{regex})")
        self.regex = re.compile("|".join(regexes))

    def lex(self, text: str) -> Iterator[Token]:
        for match in self.regex.finditer(text):
            group = match.lastgroup
            token_type = st_token_type_to_int[group]
            if token_type in IGNORED_TERMINALS:
                continue
            value = match.group(group)
            yield Token(token_type, value, pos=match.start())


# %%

class JavaParser:
    bracket_stack: List[str]
    def __init__(self) -> None:
        self.bracket_stack = []

# %%

res = JavaLexer().lex("""
class Foo implements extends bla bla {

}
""")
list(res)