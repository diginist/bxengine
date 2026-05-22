from dataclasses import dataclass
from typing import List
from bxengine.spans import SpanData

class Node:
    pass

class Nodes:
    @dataclass(frozen=True)
    class Error(Node):
        message: str
        range: SpanData

    """
    This is only used internally, package users do not need to handle _Complete.
    """
    @dataclass(frozen=True)
    class _Complete(Node):
        range: SpanData

    @dataclass(frozen=True)
    class OuterText(Node):
        value: str
        range: SpanData

    @dataclass(frozen=True)
    class Function(Node):
        name: str
        arguments: List[Node]
        range: SpanData

    @dataclass(frozen=True)
    class Number(Node):
        value: str
        range: SpanData

    @dataclass(frozen=True)
    class StringNode(Node):
        value: str
        range: SpanData
