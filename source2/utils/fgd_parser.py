import itertools
from enum import Enum
from typing import Union, Tuple
from pathlib import Path

from SourceIO.source_shared.content_manager import ContentManager


class FGDLexerException(Exception):
    pass


class FGDParserException(Exception):
    pass


class FGDToken(Enum):
    STRING = "String literal"
    NUMERIC = "Numeric literal"
    IDENTIFIER = "Identifier literal"
    KEYWORD = "Keyword literal"
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"
    EQUALS = "="
    COLON = ":"
    PLUS = "+"
    MINUS = "-"
    COMMA = ","
    DOT = "."
    FSLASH = "/"
    BSLASH = "\\"
    EOF = "End of file"


class FGDLexer:

    def __init__(self, buffer: str, buffer_name: str = '<memory>'):
        self.buffer = buffer
        self.buffer_name = buffer_name
        self._offset = 0
        self._line_char_id = 1
        self._line_id = 1

    @property
    def symbol(self):
        if self._offset < len(self.buffer):
            return self.buffer[self._offset]
        else:
            return ""

    @property
    def next_symbol(self):
        if self._offset + 1 < len(self.buffer):
            return self.buffer[self._offset + 1]
        else:
            return ""

    @property
    def leftover(self):
        return self.buffer[self._offset:]

    @property
    def line_id(self):
        return self._line_id

    @property
    def char_id(self):
        return self._line_char_id

    def advance(self, count=1):
        buffer = ""
        for _ in range(count):
            sym = self.symbol
            self._line_char_id += 1
            if sym == '\n':
                self._line_id += 1
                self._line_char_id = 1
            self._offset += 1
            buffer += sym
        return buffer

    def lex(self):
        while self._offset < len(self.buffer):
            if self.symbol == '"':
                self.advance()
                string_buffer = ""
                while True:
                    if self.symbol == '"':
                        self.advance()
                        break
                    string_buffer += self.advance()
                yield FGDToken.STRING, string_buffer
            elif self.symbol.isspace():
                self.advance()
            elif self.symbol.isdigit() or (self.symbol == '-' and self.next_symbol.isdigit()):
                num_buffer = ""
                while self.symbol.isdigit() or (self.symbol == '-' and self.next_symbol.isdigit()):
                    num_buffer += self.advance()
                yield FGDToken.NUMERIC, int(num_buffer)
            elif self.symbol.isidentifier():
                string_buffer = self.advance()
                while True:
                    if self.symbol.isspace() or not (self.symbol.isidentifier() or self.symbol.isdigit()):
                        break
                    string_buffer += self.advance()
                yield FGDToken.IDENTIFIER, string_buffer
            elif self.symbol == "@" and self.next_symbol.isidentifier():
                string_buffer = self.advance()
                while True:
                    if self.symbol.isspace() or not self.symbol.isidentifier():
                        break
                    string_buffer += self.advance()
                yield FGDToken.KEYWORD, string_buffer
            elif self.symbol == '/' and self.next_symbol == '/':
                while True:
                    if self.symbol == '\n':
                        break
                    self.advance()
            elif self.symbol == '/' and self.next_symbol == '*':
                self.advance(2)
                while True:
                    if self.symbol == '*' and self.next_symbol == '/':
                        self.advance(2)
                        break
                    self.advance()
            elif self.symbol == '{':
                yield FGDToken.LBRACE, self.advance()
            elif self.symbol == '}':
                yield FGDToken.RBRACE, self.advance()
            elif self.symbol == '(':
                yield FGDToken.LPAREN, self.advance()
            elif self.symbol == ')':
                yield FGDToken.RPAREN, self.advance()
            elif self.symbol == '[':
                yield FGDToken.LBRACKET, self.advance()
            elif self.symbol == ']':
                yield FGDToken.RBRACKET, self.advance()
            elif self.symbol == '=':
                yield FGDToken.EQUALS, self.advance()
            elif self.symbol == ':':
                yield FGDToken.COLON, self.advance()
            elif self.symbol == '-':
                yield FGDToken.MINUS, self.advance()
            elif self.symbol == '+':
                yield FGDToken.PLUS, self.advance()
            elif self.symbol == ',':
                yield FGDToken.COMMA, self.advance()
            elif self.symbol == '.':
                yield FGDToken.DOT, self.advance()
            elif self.symbol == '/':
                yield FGDToken.FSLASH, self.advance()
            elif self.symbol == '\\':
                yield FGDToken.BSLASH, self.advance()
            else:
                raise FGDLexerException(
                    f'Unknown symbol "{self.symbol}" in "{self.buffer_name}" at {self._line_id}:{self._line_char_id}')
        yield FGDToken.EOF, None

    def __bool__(self):
        return self._offset < len(self.buffer)


class FGDParser:
    def __init__(self, path: Union[Path, str] = None, buffer_and_name: Tuple[str, str] = None):
        if path is not None:
            self._path = Path(path)
            with self._path.open() as f:
                self._lexer = FGDLexer(f.read(), str(self._path))
        elif buffer_and_name is not None:
            self._lexer = FGDLexer(*buffer_and_name)
            self._path = buffer_and_name[1]
        self._tokens = self._lexer.lex()
        self._last_peek = None

        self.classes = []
        self.excludes = []
        self.pragmas = {}
        self.includes = []

    def peek(self):
        if self._last_peek is None:
            self._last_peek = next(self._tokens)
        return self._last_peek

    def advance(self):
        if self._last_peek is not None:
            ret = self._last_peek
            self._last_peek = None
            return ret
        return next(self._tokens)

    def expect(self, token_type):
        token, value = self.peek()
        if token == token_type:
            self.advance()
            return value
        else:
            raise FGDParserException(
                f"Unexpected token {token_type}, got {token}:\"{value}\" in {self._path} at {self._lexer.line_id}:{self._lexer.char_id}")

    def match(self, token_type):
        token, value = self.peek()
        return token == token_type

    def parse(self):
        while self._lexer:
            if self.match(FGDToken.KEYWORD):
                _, value = self.advance()
                if value == '@mapsize':
                    self.expect(FGDToken.LPAREN)
                    max_x = self.expect(FGDToken.NUMERIC)
                    self.expect(FGDToken.COMMA)
                    max_y = self.expect(FGDToken.NUMERIC)
                    self.expect(FGDToken.RPAREN)
                    self.pragmas['mapsize'] = (max_x, max_y)
                elif value.lower() == "@include":
                    include = self.expect(FGDToken.STRING)
                    file = ContentManager().find_file(include)
                    if file is not None:
                        parsed_include = FGDParser(buffer_and_name=(file.read().decode("ascii"), include))
                        parsed_include.parse()
                        self.classes.extend(parsed_include.classes)
                        self.pragmas.update(parsed_include.pragmas)
                        self.excludes.extend(parsed_include.excludes)
                        self.includes.append(include)
                elif value.lower() == '@exclude':
                    self.excludes.append(self.expect(FGDToken.IDENTIFIER))
                elif value.lower() == '@entitygroup':
                    pragma = self.pragmas[self.expect(FGDToken.STRING)] = {}
                    if self.match(FGDToken.LBRACE):
                        self.advance()
                        while not self.match(FGDToken.RBRACE):
                            key = self.expect(FGDToken.IDENTIFIER)
                            self.expect(FGDToken.EQUALS)
                            value = self.expect(FGDToken.IDENTIFIER)
                            pragma[key] = value
                        self.advance()
                elif value.startswith('@') and value.lower().endswith("class"):
                    self._parse_baseclass()
            elif self.match(FGDToken.EOF):
                break
            else:
                token, value = self.peek()
                raise FGDParserException(
                    f"Unexpected token {token}:\"{value}\" in {self._path} at {self._lexer.line_id}:{self._lexer.char_id}")
            # print(self.advance())

    def _parse_baseclass(self):

        class_def = {'io': {}, 'props': {}, 'bases': [], 'meta_props': {}}
        if self.match(FGDToken.IDENTIFIER):
            while not self.match(FGDToken.EQUALS):
                pre_prop_type = self.expect(FGDToken.IDENTIFIER)
                if pre_prop_type == 'base':
                    class_def['bases'] = self._parse_bases()
                elif pre_prop_type == 'color':
                    self.expect(FGDToken.LPAREN)
                    r = self.expect(FGDToken.NUMERIC)
                    g = self.expect(FGDToken.NUMERIC)
                    b = self.expect(FGDToken.NUMERIC)
                    self.expect(FGDToken.RPAREN)
                    class_def['meta_props'][pre_prop_type] = (r, g, b)
                elif pre_prop_type == 'metadata':
                    class_def['meta_props'][pre_prop_type] = {}
                    self.expect(FGDToken.LBRACE)
                    while not self.match(FGDToken.RBRACE):
                        key = self.expect(FGDToken.IDENTIFIER)
                        self.expect(FGDToken.EQUALS)
                        value = self.expect(FGDToken.STRING)
                        class_def['meta_props'][pre_prop_type][key] = value
                    self.expect(FGDToken.RBRACE)
                else:
                    if self.match(FGDToken.LPAREN):
                        self.expect(FGDToken.LPAREN)
                        class_def['meta_props'][pre_prop_type] = []
                        while not self.match(FGDToken.RPAREN):
                            class_def['meta_props'][pre_prop_type].append(self.advance()[1])
                            if self.match(FGDToken.COMMA):
                                self.advance()
                        self.expect(FGDToken.RPAREN)
                    else:
                        class_def['meta_props'][pre_prop_type] = True

        self.expect(FGDToken.EQUALS)
        class_def['name'] = self.expect(FGDToken.IDENTIFIER)

        if self.match(FGDToken.COLON):
            self.advance()
            if self.match(FGDToken.STRING):
                class_def['doc'] = self._parse_joined_string()

        self.expect(FGDToken.LBRACKET)
        while self.match(FGDToken.IDENTIFIER):
            token, ident = self.peek()
            if token == FGDToken.IDENTIFIER and ident in ['input', 'output']:
                self._parse_class_io(class_def['io'])
            elif self.match(FGDToken.IDENTIFIER):
                name = self._parse_fully_qualified_identifier()
                prop = class_def['props'][name] = {}
                self._parse_class_param(prop)
        self.expect(FGDToken.RBRACKET)
        self.classes.append(class_def)

    def _parse_fully_qualified_identifier(self):
        p1 = self.expect(FGDToken.IDENTIFIER)
        while self.match(FGDToken.DOT):
            self.advance()
            p1 += '.' + self.expect(FGDToken.IDENTIFIER)
        return p1

    def _parse_fully_qualified_type(self):
        p1 = self.expect(FGDToken.IDENTIFIER)
        while self.match(FGDToken.COLON):
            self.advance()
            p1 += '.' + self.expect(FGDToken.IDENTIFIER)
        return p1

    def _parse_joined_string(self):
        p1 = self.expect(FGDToken.STRING)
        while self.match(FGDToken.PLUS):
            self.advance()
            p1 += self.expect(FGDToken.STRING)
        return p1

    def _parse_bases(self):
        bases = []
        self.expect(FGDToken.LPAREN)
        while not self.match(FGDToken.RPAREN):
            bases.append(self.expect(FGDToken.IDENTIFIER))
            if not self.match(FGDToken.COMMA):
                self.expect(FGDToken.RPAREN)
                break
            elif self.match(FGDToken.COMMA):
                self.advance()
        return bases

    def _parse_class_io(self, storage):
        io_type = self.expect(FGDToken.IDENTIFIER)
        name = self.expect(FGDToken.IDENTIFIER)
        self.expect(FGDToken.LPAREN)
        args = []
        while not self.match(FGDToken.RPAREN):
            args.append(self.expect(FGDToken.IDENTIFIER))
        self.expect(FGDToken.RPAREN)
        if self.match(FGDToken.COLON):
            self.advance()
            doc_str = self._parse_joined_string() if self.match(FGDToken.STRING) else None
            storage[name] = {'type': io_type, 'args': args, 'doc': doc_str}

    def _parse_class_param(self, storage):
        self.expect(FGDToken.LPAREN)
        param_type = self._parse_fully_qualified_type()
        self.expect(FGDToken.RPAREN)
        meta = {}
        if self.match(FGDToken.LBRACKET):
            self.advance()
            while not self.match(FGDToken.RBRACKET):
                name = self.expect(FGDToken.IDENTIFIER)
                if self.match(FGDToken.EQUALS):
                    self.advance()
                    value = self.expect(FGDToken.STRING)
                else:
                    value = True
                meta[name] = value
                if self.match(FGDToken.COMMA):
                    self.advance()
            self.expect(FGDToken.RBRACKET)
        data = []
        if self.match(FGDToken.COLON):
            self.advance()
            while self.match(FGDToken.STRING) or self.match(FGDToken.NUMERIC) or self.match(
                    FGDToken.COLON) or self.match(FGDToken.PLUS):
                if self.match(FGDToken.COLON):
                    self.advance()
                    continue
                elif self.match(FGDToken.PLUS):
                    self.advance()
                    dt = self.expect(FGDToken.STRING)
                    while self.match(FGDToken.PLUS):
                        self.expect(FGDToken.PLUS)
                        dt += self.expect(FGDToken.STRING)
                    data.append(dt)
                else:
                    data.append(self.advance())
        if self.match(FGDToken.EQUALS) and param_type.lower() == 'choices':
            # parse choices
            self.advance()
            self.expect(FGDToken.LBRACKET)
            choices = {}
            while not self.match(FGDToken.RBRACKET):
                name = self.expect(FGDToken.STRING) if self.match(FGDToken.STRING) else self.expect(FGDToken.NUMERIC)
                self.expect(FGDToken.COLON)
                value = self.expect(FGDToken.STRING)
                choices[name] = value
            self.expect(FGDToken.RBRACKET)
            storage['choices'] = choices
        elif self.match(FGDToken.EQUALS) and param_type.lower() == 'flags':
            # parse flags
            self.advance()
            self.expect(FGDToken.LBRACKET)
            flags = {}
            while not self.match(FGDToken.RBRACKET):
                mask = self.expect(FGDToken.NUMERIC)
                self.expect(FGDToken.COLON)
                name = self.expect(FGDToken.STRING)
                self.expect(FGDToken.COLON)
                default = self.expect(FGDToken.NUMERIC)

                flags[name] = (mask, default)
            self.expect(FGDToken.RBRACKET)
            storage['flags'] = flags
        elif self.match(FGDToken.EQUALS) and param_type.lower() == 'tag_list':
            # parse flags
            self.advance()
            self.expect(FGDToken.LBRACKET)
            flags = {}
            while not self.match(FGDToken.RBRACKET):
                mask = self.expect(FGDToken.STRING)
                self.expect(FGDToken.COLON)
                name = self.expect(FGDToken.STRING)
                self.expect(FGDToken.COLON)
                default = self.expect(FGDToken.NUMERIC)

                flags[name] = (mask, default)
            self.expect(FGDToken.RBRACKET)
            storage['tag_list'] = flags
        storage['type'] = param_type
        storage['meta'] = meta
        storage['data'] = data


if __name__ == '__main__':
    test_file = Path(r"F:\SteamLibrary\steamapps\common\Half-Life Alyx\game\hlvr\hlvr.fgd")
    ContentManager().scan_for_content(test_file)
    parser = FGDParser(test_file)
    parser.parse()
    pass
