from dataclasses import dataclass

from bxengine.spans import SpanData


class Token:
    pass

class Tokens:
    @dataclass(frozen=True)
    class Error(Token):
        message: str
        range: SpanData

    @dataclass(frozen=True)
    class EndOfFile(Token):
        range: SpanData

    @dataclass(frozen=True)
    class OuterString(Token):
        value: str
        range: SpanData

    @dataclass(frozen=True)
    class QuotedString(Token):
        value: str
        range: SpanData

    @dataclass(frozen=True)
    class UnquotedString(Token):
        value: str
        range: SpanData

    @dataclass(frozen=True)
    class Number(Token):
        value: str
        range: SpanData

    @dataclass(frozen=True)
    class OpenBracket(Token):
        range: SpanData

    @dataclass(frozen=True)
    class CloseBracket(Token):
        range: SpanData
