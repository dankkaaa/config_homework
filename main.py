import argparse
import json
import sys


class Token:
    def __init__(self, kind, value, pos):
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r}, {self.pos})"


class LexerError(Exception):
    pass


class ParserError(Exception):
    pass


KEYWORDS = {"def", "struct"}


class Lexer:
    def __init__(self, text):
        self.text = text
        self.n = len(text)
        self.i = 0

    def _peek(self, k=0):
        pos = self.i + k
        if pos >= self.n:
            return ""
        return self.text[pos]

    def _consume_while(self, predicate):
        start = self.i
        while self.i < self.n and predicate(self.text[self.i]):
            self.i += 1
        return self.text[start:self.i]

    def _skip_whitespace_and_comments(self):
        while self.i < self.n:
            ch = self._peek()
            if ch.isspace():
                self.i += 1
                continue

            # однострочный комментарий: REM ... до конца строки
            if self.text.startswith("REM", self.i):
                before = self.text[self.i - 1] if self.i > 0 else " "
                if before.isspace() or before in "{}();,.":
                    while self.i < self.n and self._peek() != "\n":
                        self.i += 1
                    continue


            if self.text.startswith("--[[", self.i):
                self.i += 4
                end_pos = self.text.find("]]", self.i)
                if end_pos == -1:
                    raise LexerError("Не закрыт многострочный комментарий '--[['")
                self.i = end_pos + 2
                continue

            break

    def tokens(self):
        result = []
        self._skip_whitespace_and_comments()
        while self.i < self.n:
            ch = self._peek()
            pos = self.i

            # идентификаторы и ключевые слова
            if ch.isalpha():
                ident = self._consume_while(lambda c: c.isalnum())
                kind = "KEYWORD" if ident in KEYWORDS else "ID"
                result.append(Token(kind, ident, pos))

            # числа (только целые, с необязательным +/-)
            elif ch in "+-" or ch.isdigit():
                # знак
                if ch in "+-":
                    sign = ch
                    self.i += 1
                    if not self._peek().isdigit():
                        raise LexerError(f"Ожидалась цифра после знака в позиции {pos}")
                    digits = sign + self._consume_while(lambda c: c.isdigit())
                else:
                    digits = self._consume_while(lambda c: c.isdigit())

                # проверка формата: 0 или не начинающееся с 0
                if len(digits.lstrip("+-")) > 1 and digits.lstrip("+-").startswith("0"):
                    raise LexerError(f"Неверный формат числа '{digits}' в позиции {pos}")
                result.append(Token("NUMBER", int(digits), pos))

            # строки в одинарных кавычках
            elif ch == "'":
                self.i += 1
                start = self.i
                while self.i < self.n and self._peek() != "'":
                    # без экранирования, просто ищем следующую '
                    if self._peek() == "\n":
                        raise LexerError(f"Строка не закрыта (новая строка) из позиции {pos}")
                    self.i += 1
                if self.i >= self.n:
                    raise LexerError(f"Строка не закрыта до конца файла, позиция {pos}")
                text = self.text[start:self.i]
                self.i += 1  # закрывающая кавычка
                result.append(Token("STRING", text, pos))

            # одиночные символы
            elif ch in "{}()=,;.":
                self.i += 1
                result.append(Token("SYMBOL", ch, pos))

            else:
                raise LexerError(f"Неизвестный символ '{ch}' в позиции {pos}")

            self._skip_whitespace_and_comments()

        result.append(Token("EOF", "", self.n))
        return result


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0
        self.consts = {}

    def _peek(self, k=0):
        return self.toks[self.i + k]

    def _eat(self, expected_kind=None, expected_value=None):
        tok = self._peek()
        if expected_kind is not None and tok.kind != expected_kind:
            raise ParserError(
                f"Ожидался токен типа {expected_kind}, а получен {tok.kind} в позиции {tok.pos}"
            )
        if expected_value is not None and tok.value != expected_value:
            raise ParserError(
                f"Ожидался символ/слово '{expected_value}', а получено '{tok.value}' в позиции {tok.pos}"
            )
        self.i += 1
        return tok

    def parse_program(self):
        while self._peek().kind != "EOF":
            self.parse_def_stmt()
        return self.consts

    def parse_def_stmt(self):
        self._eat("SYMBOL", "(")
        self._eat("KEYWORD", "def")
        name_tok = self._eat("ID")
        name = name_tok.value
        value = self.parse_value()
        self._eat("SYMBOL", ")")
        self._eat("SYMBOL", ";")

        # сохраняем вычисленное значение в окружении
        self.consts[name] = value

    def parse_value(self):
        tok = self._peek()

        # число
        if tok.kind == "NUMBER":
            self._eat("NUMBER")
            return tok.value

        # строка
        if tok.kind == "STRING":
            self._eat("STRING")
            return tok.value

        # struct { ... }
        if tok.kind == "KEYWORD" and tok.value == "struct":
            return self.parse_struct()

        # подстановка константы: . ( ID ) .
        if tok.kind == "SYMBOL" and tok.value == ".":
            return self.parse_const_ref()

        raise ParserError(f"Ожидалось значение (число, строка, struct или .(имя).) в позиции {tok.pos}")

    def parse_struct(self):
        self._eat("KEYWORD", "struct")
        self._eat("SYMBOL", "{")
        obj = {}

        # пустой struct не описан, но поддержим вариант без полей
        if self._peek().kind == "SYMBOL" and self._peek().value == "}":
            self._eat("SYMBOL", "}")
            return obj

        while True:
            key_tok = self._eat("ID")
            key = key_tok.value
            self._eat("SYMBOL", "=")
            val = self.parse_value()
            obj[key] = val

            tok = self._peek()
            if tok.kind == "SYMBOL" and tok.value == ",":
                self._eat("SYMBOL", ",")
                # допускаем завершающую запятую перед '}'
                if self._peek().kind == "SYMBOL" and self._peek().value == "}":
                    break
                continue
            else:
                break

        self._eat("SYMBOL", "}")
        return obj

    def parse_const_ref(self):
        """
        const_ref := '.' '(' ID ')' '.'
        """
        self._eat("SYMBOL", ".")
        self._eat("SYMBOL", "(")
        name_tok = self._eat("ID")
        self._eat("SYMBOL", ")")
        self._eat("SYMBOL", ".")
        name = name_tok.value
        if name not in self.consts:
            raise ParserError(
                f"Использование неопределённой константы '{name}' в позиции {name_tok.pos}"
            )
        return self.consts[name]


def translate(input_text):
    # лексический анализ
    lexer = Lexer(input_text)
    tokens = lexer.tokens()

    parser = Parser(tokens)
    env = parser.parse_program()

    return json.dumps(env, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(
        description="Транслятор учебного конфигурационного языка в JSON (вариант 6)"
    )
    ap.add_argument("--input", "-i", required=True, help="путь к входному файлу")
    ap.add_argument("--output", "-o", required=True, help="путь к выходному JSON‑файлу")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
        json_text = translate(text)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_text)
    except (LexerError, ParserError) as e:
        print("Синтаксическая ошибка:", e, file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print("Ошибка ввода‑вывода:", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
