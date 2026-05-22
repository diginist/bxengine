from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from bxengine.runtime.executor import Executor, FunctionEntry


@dataclass
class RuntimeContext:
    local_variables: dict[str, Any] = field(default_factory=dict)
    program_args: list[Any] = field(default_factory=list)
    executor: Executor | None = None
    functions: dict[str, FunctionEntry] = field(default_factory=dict)
    last_exception: Exception | None = None
