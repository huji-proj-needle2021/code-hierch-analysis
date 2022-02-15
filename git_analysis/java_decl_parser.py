""" In this module we implement a parser for Java class/interface/enum and method declarations.
    This involves two stages:

    - First, we use Regex in order to lex the source code, this allows us to get rid
      of comments, whitespace, string literals(which might be confused for part of code)
      and identify interesting tokens, while maintaining their position in the original text.
      
      We don't gather the full lexical structure of Java,as we really care about few elements:
      identifiers, class keywords, and other elements that help us guide the parser.

    - The parser itself is roughly based on recursive descent(and thus can deal with nested
      classes), but since we do not care about most of the Java grammar, it involves a 
      lot of skipping ahead. Namely, whenever a `class` keyword is encountered, we begin
      parsing for a class. Whenever we encounter a parameter list, we parse a method(and
      ignore the contents of the method's body). We also parse(and ignore) annotations
      and field assignments, since they may also have parameter lists which might
      be confused as methods.

"""
import re
from enum import IntEnum, auto
from typing import Iterable, Iterator, NamedTuple, List, Optional, Tuple, Union
from .java_type import JavaFile, JavaHierarchy, JavaClass, JavaMethod
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
OPENING_SEP = OPENING_TO_CLOSING_SEP.keys()

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
    """ Regex based lexer that partially handles Java """
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



CLASS_KEYWORDS = set(["class", "interface", "enum"])

class ParseException(Exception):
    pass

class NoMatchingParen(ParseException):
    pass

class CouldntSkip(ParseException):
    pass

class UnexpectedElement(ParseException):
    pass

UNKNOWN_PACKAGE_NAME = "!UNKNOWN_PACKAGE!"

class JavaParser:
    """ Parses class and method declarations in a Java file """
    def __init__(self):
        self.tokens: List[Token] = []
        self.lexer = JavaLexer()
        self.text = ""

    def parse_java(self, text: str) -> JavaHierarchy:
        self.text = text
        self.tokens = list(self.lexer.lex(text))
        return self._parse_file()

    def parse_java_bytes(self, contents: bytes) -> JavaHierarchy:
        text = contents.decode('latin-1', 'replace')
        self.text = text
        return self.parse_java(text)

    def __getitem__(self, key):
        if key < 0:
            return "UNDERFLOW"
        if key >= len(self.tokens):
            return "EOF"
        return self.tokens[key]

    def _set_tokens(self, tokens: List[Token]):
        self.tokens = tokens
    
    def _parse_file(self) -> JavaHierarchy:
        i = 0
        package_name = UNKNOWN_PACKAGE_NAME
        members = []
        try:
            while i < len(self.tokens):
                if (self.tokens[i].type == TokenType.KEYWORD and
                    self.tokens[i].value == "package"
                    ):
                    i, package = self._parse_dot_delimited_identifiers(i + 1)
                    package_name = ".".join(package)

                elif (self.tokens[i].type == TokenType.KEYWORD and
                    self.tokens[i].value in CLASS_KEYWORDS
                    ):
                    class_end_brack, clazz = self._try_parse_class(i)
                    i = class_end_brack + 1
                    if clazz is not None:
                        members.append(clazz)
                else:
                    i += 1
        except Exception as e:
            log.error(f"Error while parsing: {e}")
        clazz = JavaFile(package_name, start=0, end=i, members=members)
        for member in clazz.members:
            member.parent = clazz
        return clazz

    def _parse_dot_delimited_identifiers(self, pos: int) -> Tuple[int, List[str]]:
        """ Parses a list of dot delimited identifiers starting at given token index,
            returns them tupled with the index past the last parsed token. """
        
        assert self.tokens[pos].type == TokenType.IDENTIFIER
        idents = [self.tokens[pos].value]
        next_tok = pos + 1
        while next_tok < len(self.tokens) and self.tokens[next_tok].value == ".":
            if self.tokens[next_tok + 1].type != TokenType.IDENTIFIER:
                raise UnexpectedElement("Expected identifier after dot, got ",
                                        f"{self[next_tok + 1]} instead")
            idents.append(self.tokens[next_tok + 1].value)
            next_tok = next_tok + 2
        
        return next_tok, idents

    def _try_parse_class(self, pos: int) -> Tuple[int, Optional[JavaHierarchy]]:
        """ Tries to parse a class/interface/enum, whose keyword appears at the given position. 
            Also returns the highest token index that was scanned during this parsing - that of 
            the closing bracket(if the class was parsed successfully), otherwise of the last token
            seen by this method.
        """
        if pos - 1 > 0 and self.tokens[pos - 1].value == ".":
            # we matched ".class", skip
            return pos, None
        if self.tokens[pos + 1].type != TokenType.IDENTIFIER:
            log.warning(f"Expected to see an identifier after class/interface keyword")
            raise UnexpectedElement("Expected to see an identifier after class/interface keyword, "
                                    f"instead got {self[pos+1]}")
        class_type = self.tokens[pos].value
        name = self.tokens[pos + 1].value
        log.debug(f"Parsing class of type {class_type}, name: {name}")

        # finding the opening bracket - there may be generic or extends/implements inbetween
        brack_ix = self._skip_to(pos + 2, TokenType.SEPARATOR, "{")
        end_ix, members = self._parse_members(class_type, brack_ix + 1)

        class_keyword_pos = self.tokens[pos].pos
        end_brack_pos = self.tokens[end_ix].pos if end_ix >= 0 else self.tokens[-1].pos

        # TODO: find an earlier starting position (modifiers and annotations belonging to class)
        clazz = JavaClass(start=class_keyword_pos, end=end_brack_pos + 1, name=name, members=members)
        for member in members:
            member.parent = clazz
        return end_ix, clazz
    

    def _try_parse_method(self, class_kind: str, open_paren_ix: int, 
                         lower_bound: int=0) -> Tuple[int, Optional[JavaHierarchy]]:
        """ Tries to parse a method/ctor when given a parameter list. A lower index bound specifiying the minimal
            starting position(one past the ending of the previous member in the block) is given to prevent unnecessary backtracking.
            
            The method returns the highest index which was scanned, in either case of failure or success - this allows
            the parser to continue efficiently without repeating seen elements.
            
            In contrast to parsing a class, this method is a bit inefficient due to use of backtracking, consider the following case:
            pkg.foo.bar.ClsA.ClsB foo(); // abstract or interface method that returns ClsB
            in contrast to a method call
            int k = pkg.foo.bar.ClsA.ClsB.foo();
            or even a lambda
            var lambdaDef = (int a, int b) -> {};
        """
        log.debug(f"Trying to parse suspected method whose paren begins at {open_paren_ix}, lower bound: {lower_bound}, belonging to class type {class_kind}")
        closing_paren_ix = self._find_closing_bracket(open_paren_ix)
        opening_brack_or_sc_ix = self._skip_to(closing_paren_ix + 1, TokenType.SEPARATOR, [";", "{"])
        if open_paren_ix - 1 < 0 or self.tokens[open_paren_ix - 1].type != TokenType.IDENTIFIER:
            raise UnexpectedElement("Expected an identifier before opening paren, "
                                    f"instead got {self[open_paren_ix - 1]}")

        method_ident_tok = self.tokens[open_paren_ix - 1]
        closer_ix = opening_brack_or_sc_ix
        if self.tokens[opening_brack_or_sc_ix].value == "{":
            closer_ix = self._find_closing_bracket(opening_brack_or_sc_ix)
            if self.tokens[opening_brack_or_sc_ix - 1].value == "->":
                log.debug("False positive, found lambda")
                return closer_ix, None

        return closer_ix, JavaMethod(start=method_ident_tok.pos, end=self.tokens[closer_ix].pos + 1, name=method_ident_tok.value)

    def _skip_to(self, from_pos: int, token_type: TokenType, values: Iterable[str]) -> int:
        """ Looks for a token matching given criteria from a given starting position, returns its
            index, or the index of the last token if no match was found. In case of encountering skipping over a paren/bracket(that isn't
            the target value being skipped to), will skip towards the matching closing bracket - ignoring everything between.
            it.
            """
        i = from_pos
        while i < len(self.tokens):
            if self.tokens[i].type == token_type and self.tokens[i].value in values:
                return i
            elif self.tokens[i].type == TokenType.SEPARATOR and self.tokens[i].value in OPENING_TO_CLOSING_SEP.keys():
                # if i - 1 > 0 and self.tokens[i].value == "{" and self.tokens[i-1].value != "->":
                #     ctx = self.text[self.tokens[i-10].pos : self.tokens[i+10].pos]
                #     log.warn(f"Skipped a block that does not follow a lambda, context: {ctx}")
                i = self._find_closing_bracket(i) + 1
            else:
                i += 1

        raise CouldntSkip(f"Couldn't skip to {token_type} of value in {values} "
                          f"starting from {from_pos}, skipped to end of text")

    def _try_skip_annotation(self, at_symbol_pos: int) -> int:
        """ Tries to parse an annotation given the position of the "@" token, 
            and returns the token index after that annotation, or just one past the given index if no annotation was parsed."""
        if at_symbol_pos + 1 == len(self.tokens):
            return at_symbol_pos + 1
        if self.tokens[at_symbol_pos + 1].value == "interface":
            # @interface is an annotation definition, which we will parse as a class
            return at_symbol_pos + 1
        elif self.tokens[at_symbol_pos + 1].type != TokenType.IDENTIFIER:
            raise UnexpectedElement(("Expected 'interface' or identifier after '@' symbol, "
                                     f"got {self[at_symbol_pos + 1]} instead"))
        
        # start parsing the annotation's type name - an annotation type
        # cannot be generic, so it's basically dot delimited identifiers

        after_ident_pos = at_symbol_pos + 2
        while after_ident_pos < len(self.tokens) and self.tokens[after_ident_pos].value == ".":
            if after_ident_pos + 1 == len(self.tokens) or self.tokens[after_ident_pos + 1].type != TokenType.IDENTIFIER:
                raise UnexpectedElement("Expected identifier after dot separator, got "
                                        f"{self[after_ident_pos + 1]} instead")
            after_ident_pos = after_ident_pos + 2
        
        if after_ident_pos < len(self.tokens) and self.tokens[after_ident_pos].value == "(":
            # annotation with parameter list - skip to end of list
            closing_paren = self._find_closing_bracket(after_ident_pos)
            return closing_paren + 1
        return after_ident_pos

    def _parse_members(self, class_type: str, pos_after_brack: int) -> Tuple[int, List[JavaHierarchy]]:
        """ Parses a list of method/class declarations in a class/interface/enum block
            (as specified in `class_type`) starting at given index.
            Returns the index of the closing bracket tupled with a list of parsed members, or -1 as index
            if no closing bracket was found.
        """
        members: List[JavaHierarchy] = []
        i = pos_after_brack
        min_bound = pos_after_brack
        while i < len(self.tokens):
            try:
                token = self.tokens[i]
                # reached end of current member block
                if token.type == TokenType.SEPARATOR and token.value == "}":
                    return i, members
                # We almost definitely have a class
                if token.type == TokenType.KEYWORD and token.value in CLASS_KEYWORDS:
                    i, clazz = self._try_parse_class(i)
                    i += 1
                    if clazz is not None:
                        members.append(clazz)
                        min_bound = i
                # We skip field assignment (as it may have a parameter list due to function invocation, 
                # # or a lambda definition which could confuse the parser)
                elif token.type == TokenType.OPERATOR and token.value == "=":
                    i = self._skip_to(i + 1, TokenType.SEPARATOR, (";",)) + 1
                # skip an annotation (as it may have a parameter list)
                elif token.type == TokenType.SEPARATOR and token.value == "@":
                    i = self._try_skip_annotation(i)
                # We have a function call (based on parameter list)
                elif token.type == TokenType.SEPARATOR and token.value == "(":
                    i, method = self._try_parse_method(class_type, i, min_bound)
                    i += 1
                    if method is not None:
                        members.append(method)
                        min_bound = i
                
                # We found a block that doesn't belong to a class or method(e.g, a static block or
                # a lambda function declaration), skip to the block's ending.
                elif token.type == TokenType.SEPARATOR and token.value == "{":
                    i = self._find_closing_bracket(i) + 1
                    min_bound = i
                else:
                    i += 1
            except NoMatchingParen as e:
                log.error(f"Found unmatched paren when parsing members, terminating parse: {e}")
                return -1, members
            except ParseException as e:
                log.warning(f"Got parse exception while parsing members, skipping ahead: {e}")
                i += 1

        log.warning("Couldn't find ending bracket for member block, assuming end of text to be class ending")
        return -1, members


    def _find_closing_bracket(self, starting_bracket_pos: int) -> int:
        """ Given the position of a starting paren/bracket, finds the index of the corresponding ending
            bracket. Returns None if no closing bracket is found. """
        assert (self.tokens[starting_bracket_pos].value in OPENING_SEP)
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
        raise NoMatchingParen(f"Found un-matched paren/bracket starting at position {starting_bracket_pos}, "
                              f"number of nested openers: {n_nested_openers}")

