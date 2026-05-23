#!/usr/bin/env python3
"""Comparison harness: runs each B++ program through old and new engines with fixed seeds."""

import sys
import os
import random
import signal
import traceback
import time
import copy
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPAT_DIR = os.path.join(ROOT, "tests", "compat")
OLD_VER_DIR = os.path.join(COMPAT_DIR, "old_ver")

sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, COMPAT_DIR)
sys.path.insert(1, OLD_VER_DIR)

import _db as _db_module
_db_module.VARIABLES_PATH = os.path.join(ROOT, "tests", "b++2variables_1506121142510026875.txt")

import _bpp_parsing as _bpp_parsing_module
from _bpp_parsing import run_bpp_program, undo_str_array

from bxengine.tokenizer.tokenize import Tokenizer, TokenizationResult
from bxengine.parsing.parser import Parser, ParsingResult
from bxengine.runtime.executor import Executor, ExecutorResult
from bxengine.runtime.extensions.builtin import BuiltinExtension
from bxengine.runtime.extensions.BxeExtension import (
    BxeStatefulExtension,
    BxeRuntimeSyntaxException,
    bpp_function,
)

TESTS_DIR = os.path.join(ROOT, "tests")
PROGRAMS_FILE = os.path.join(TESTS_DIR, "b++2programs_1506121293051990057.txt")
VARIABLES_FILE = os.path.join(TESTS_DIR, "b++2variables_1506121142510026875.txt")
OUTPUT_FILE = os.path.join(TESTS_DIR, "compat", "results.log")
TYPE_LIST = [int, float, str, list]

USERNAME = "whirlingstars"
USERID = 230873196247777280
CHANNEL_ID = 481534942279630856
SEED = 42
TIMEOUT = 3
FIXED_UNIX_TIME = 1779165755.9625063


class TimeoutError(Exception):
    pass


@contextmanager
def _with_fixed_test_time():
    # Keep compat runs deterministic for clock-dependent tags.
    with (
        patch("time.time", return_value=FIXED_UNIX_TIME),
        patch.object(_bpp_parsing_module, "timenow", new=lambda: FIXED_UNIX_TIME),
    ):
        yield


def _load_initial_globals() -> tuple[dict[str, tuple[str, int, str]], dict[str, Any]]:
    raw: dict[str, tuple[str, int, str]] = {}
    typed: dict[str, Any] = {}
    with open(VARIABLES_FILE) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            name, value, vtype, owner = parts[0], parts[1], int(parts[2]), parts[3]
            raw[name] = (value, vtype, owner)
            if TYPE_LIST[vtype] == list:
                typed[name] = undo_str_array(value)
            else:
                try:
                    typed[name] = TYPE_LIST[vtype](value)
                except (ValueError, TypeError):
                    typed[name] = value
    return raw, typed


INITIAL_DB_VARIABLES, INITIAL_TYPED_GLOBALS = _load_initial_globals()


def _alarm_handler(signum, frame):
    raise TimeoutError("Timed out")


class MockRunner:
    name = USERNAME
    id = USERID

class MockChannel:
    id = CHANNEL_ID


class TestDiscordExtension(BxeStatefulExtension):
    def __init__(self):
        self.buttons: list[list[str]] = []

    @bpp_function()
    def USERNAME(self) -> str:
        return USERNAME

    @bpp_function()
    def USERID(self) -> int:
        return USERID

    @bpp_function()
    def CHANNEL(self) -> int:
        return CHANNEL_ID

    @bpp_function()
    def BUTTON(self, *args) -> str:
        self.buttons.append(list(args))
        return ""


class TestGlobalExtension(BxeStatefulExtension):
    def __init__(self):
        # Preloaded once; cloned per run to avoid reparsing the globals file ~3800x.
        self.global_variables: dict = copy.deepcopy(INITIAL_TYPED_GLOBALS)

    @bpp_function("GLOBAL")
    def global_fn(self, func_type: str, variable: str, value=None):
        match func_type.lower():
            case "define":
                self.global_variables[variable] = value
                return ""
            case "var":
                if value:
                    raise BxeRuntimeSyntaxException("GLOBAL VAR expected 2 parameters, but got 3")
                return self.global_variables[variable]
            case _:
                raise BxeRuntimeSyntaxException("GLOBAL needs a function type parameter")


class TrackingDatabase(_db_module.Database):
    last_instance = None

    def __init__(self, path=None):
        # Mirror compat DB shape without rereading/parsing the variables file each run.
        self._path = path or _db_module.VARIABLES_PATH
        self._variables = dict(INITIAL_DB_VARIABLES)
        self._tables = {"b++2variables"}
        TrackingDatabase.last_instance = self


_bpp_parsing_module.Database = TrackingDatabase


def _decode_stored_globals(raw_variables: dict[str, tuple[str, int, str]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, (value, vtype, _owner) in raw_variables.items():
        target_type = TYPE_LIST[vtype]
        if target_type is list:
            out[name] = undo_str_array(value)
        else:
            try:
                out[name] = target_type(value)
            except (ValueError, TypeError):
                out[name] = value
    return out


def _canonicalize_new_list(value: list[Any]) -> list[Any]:
    out = []
    for item in value:
        if isinstance(item, list):
            out.append(_canonicalize_new_list(item))
        else:
            out.append(str(item))
    return out


def _canonicalize_new_globals(globals_map: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in globals_map.items():
        if isinstance(value, list):
            out[key] = _canonicalize_new_list(value)
        else:
            out[key] = value
    return out


def _cut(value: Any, limit: int = 120) -> str:
    text = repr(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _summarize_globals_diff(old_globals: dict[str, Any], new_globals: dict[str, Any]) -> str:
    old_keys = set(old_globals.keys())
    new_keys = set(new_globals.keys())

    missing_in_new = sorted(old_keys - new_keys)
    extra_in_new = sorted(new_keys - old_keys)
    changed = sorted(k for k in old_keys & new_keys if old_globals[k] != new_globals[k])

    parts = []
    if missing_in_new:
        parts.append(f"missing_in_new={missing_in_new[:5]}")
    if extra_in_new:
        parts.append(f"extra_in_new={extra_in_new[:5]}")
    if changed:
        sample = []
        for key in changed[:5]:
            sample.append(f"{key}: old={_cut(old_globals[key])} new={_cut(new_globals[key])}")
        parts.append("changed=" + "; ".join(sample))

    return " | ".join(parts) if parts else "global variables differ"


def _empty_timing() -> dict[str, float]:
    return {"total": 0.0, "tokenize": 0.0, "parse": 0.0, "execute": 0.0}


def _format_span(span) -> str:
    try:
        info = span.debug_info()
        return f"{span.cursor_start}..{span.cursor_end} (line {info.start_line})"
    except Exception:
        return str(span)


def _format_error_with_span(prefix: str, message: str, span=None) -> str:
    if span is None:
        return f"{prefix}: {message}"
    return f"{prefix}: {message} @ {_format_span(span)}"


def load_programs(path):
    programs = []
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            name = parts[0]
            raw_code = parts[1]
            code = raw_code.replace("\\n", "\n")
            programs.append((name, code))
    return programs


def run_old(code):
    random.seed(SEED)
    start = time.perf_counter()
    try:
        with _with_fixed_test_time():
            TrackingDatabase.last_instance = None
            result = run_bpp_program(code, [], str(USERID), MockRunner(), MockChannel())
            db_after = TrackingDatabase.last_instance
            old_globals = (
                _decode_stored_globals(db_after._variables) if db_after is not None else {}
            )
            output = result[0]
            if isinstance(output, Exception):
                return (None, f"{type(output).__name__}: {output}", old_globals, {"total": time.perf_counter() - start})
            return (str(output), None, old_globals, {"total": time.perf_counter() - start})
    except TimeoutError:
        raise
    except Exception as e:
        return (None, f"{type(e).__name__}: {e}", {}, {"total": time.perf_counter() - start})


def run_new(code):
    random.seed(SEED)
    t0 = time.perf_counter()
    try:
        with _with_fixed_test_time():
            t_token_start = time.perf_counter()
            tok = Tokenizer.tokenize(code)
            t_token_end = time.perf_counter()
            if isinstance(tok, TokenizationResult.Error):
                return (None, _format_error_with_span("TokenizeError", tok.message, tok.range), {}, {
                    "total": time.perf_counter() - t0,
                    "tokenize": t_token_end - t_token_start,
                    "parse": 0.0,
                    "execute": 0.0,
                })
            t_parse_start = time.perf_counter()
            par = Parser.parse(code, tok.tokens)
            t_parse_end = time.perf_counter()
            if isinstance(par, ParsingResult.Error):
                return (None, _format_error_with_span("ParseError", par.message, par.range), {}, {
                    "total": time.perf_counter() - t0,
                    "tokenize": t_token_end - t_token_start,
                    "parse": t_parse_end - t_parse_start,
                    "execute": 0.0,
                })
            exe = Executor(
                extensions=[BuiltinExtension()],
                stateful_extensions=[TestGlobalExtension, TestDiscordExtension],
            )
            t_exec_start = time.perf_counter()
            result = exe.execute(par.nodes)
            t_exec_end = time.perf_counter()
            if isinstance(result, ExecutorResult.Error):
                span = getattr(result.exception, "span", None)
                return (None, _format_error_with_span(type(result.exception).__name__, str(result.exception), span), {}, {
                    "total": time.perf_counter() - t0,
                    "tokenize": t_token_end - t_token_start,
                    "parse": t_parse_end - t_parse_start,
                    "execute": t_exec_end - t_exec_start,
                })
            global_ext = next(
                (
                    ext
                    for ext in result.stateful_extensions
                    if isinstance(ext, TestGlobalExtension)
                ),
                None,
            )
            new_globals = (
                _canonicalize_new_globals(global_ext.global_variables)
                if global_ext is not None
                else {}
            )
            return (result.output, None, new_globals, {
                "total": time.perf_counter() - t0,
                "tokenize": t_token_end - t_token_start,
                "parse": t_parse_end - t_parse_start,
                "execute": t_exec_end - t_exec_start,
            })
    except TimeoutError:
        raise
    except Exception as e:
        return (None, f"{type(e).__name__}: {e}", {}, {"total": time.perf_counter() - t0, "tokenize": 0.0, "parse": 0.0, "execute": 0.0})


def normalize(s):
    if s is None:
        return None
    return s.strip()


def normalize_error(err_type):
    """Map old engine error types to new engine equivalents."""
    mappings = {
        "ProgramDefinedException": "BxeRuntimeException",
        "BxeRuntimeException": "ProgramDefinedException",
    }
    return mappings.get(err_type, err_type)


def compare(old, new):
    old_out, old_err, old_globals, _old_timing = old
    new_out, new_err, new_globals, _new_timing = new

    if old_err and new_err:
        old_type = normalize_error(old_err.split(":")[0].strip())
        new_type = new_err.split(":")[0].strip()
        return (True, "") if old_type == new_type else ("softfail", "")

    if old_err and not new_err:
        return ("softfail", "")

    if old_err or new_err:
        return (False, "")

    output_match = normalize(old_out) == normalize(new_out)
    globals_match = old_globals == new_globals

    if output_match and globals_match:
        return (True, "")
    if output_match and not globals_match:
        return (False, f"GLOBAL DIFF: {_summarize_globals_diff(old_globals, new_globals)}")
    if not output_match and globals_match:
        return (False, "OUTPUT DIFF only")
    return (False, f"OUTPUT + GLOBAL DIFF: {_summarize_globals_diff(old_globals, new_globals)}")


def main():
    programs = load_programs(PROGRAMS_FILE)
    print(f"Loaded {len(programs)} programs")

    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)

    total = 0
    passed = 0
    failed = 0
    softfailed = 0
    skipped = 0
    both_errored = 0
    timed_cases = 0
    old_total_time = 0.0
    new_total_time = 0.0
    new_tokenize_time = 0.0
    new_parse_time = 0.0
    new_execute_time = 0.0
    failed_entries: list[dict[str, str]] = []
    is_partial = False
    try:
        for name, code in programs:
            total += 1
            old = (None, "Timeout", {}, _empty_timing())
            new = (None, "Timeout", {}, _empty_timing())
            old_timed_out = False
            new_timed_out = False

            try:
                signal.alarm(TIMEOUT)
                old = run_old(code)
                signal.alarm(0)
            except TimeoutError:
                old_timed_out = True
                old = (None, "Timeout", {}, _empty_timing())
                signal.alarm(0)
            except Exception as e:
                old = (None, f"Crash: {type(e).__name__}: {e}", {}, _empty_timing())
                signal.alarm(0)

            try:
                signal.alarm(TIMEOUT)
                new = run_new(code)
                signal.alarm(0)
            except TimeoutError:
                new_timed_out = True
                new = (None, "Timeout", {}, _empty_timing())
                signal.alarm(0)
            except Exception as e:
                new = (None, f"Crash: {type(e).__name__}: {e}", {}, _empty_timing())
                signal.alarm(0)

            if old_timed_out and new_timed_out:
                skipped += 1
            elif old_timed_out or new_timed_out:
                skipped += 1

            else:
                timed_cases += 1
                old_total_time += old[3].get("total", 0.0)
                new_total_time += new[3].get("total", 0.0)
                new_tokenize_time += new[3].get("tokenize", 0.0)
                new_parse_time += new[3].get("parse", 0.0)
                new_execute_time += new[3].get("execute", 0.0)

                match, note = compare(old, new)
                if match == "softfail":
                    softfailed += 1
                elif match:
                    passed += 1
                    if old[1]:
                        both_errored += 1
                else:
                    failed += 1
                    failed_entries.append(
                        {
                            "name": name,
                            "old_err": old[1] or "",
                            "new_err": new[1] or "",
                            "old_out": normalize(old[0]) or "",
                            "new_out": normalize(new[0]) or "",
                            "note": note,
                        }
                    )

            if total % 50 == 0:
                print(f"  Progress: {total}/{len(programs)} (pass={passed} fail={failed} soft={softfailed} skip={skipped})")

        signal.signal(signal.SIGALRM, old_handler)
        OUTPUT_FILE = os.path.join(TESTS_DIR, "compat", "results.log")
    except KeyboardInterrupt:
        is_partial = True
        OUTPUT_FILE = os.path.join(TESTS_DIR, "compat", "results.partial.log")
        skipped = len(programs) - total


    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write("=== B++ Engine Comparison Results ===\n")
        f.write(f"Seed: {SEED}\n")
        f.write(f"Total: {total} | Pass: {passed} | Softfailed (ok): {softfailed} | Fail: {failed} | Skip: {skipped} | Both-errored (pass): {both_errored}\n")
        f.write("=" * 60 + "\n\n")

        for entry in failed_entries:
            f.write(f"\n\n[FAIL] {entry['name']}\n")
            if entry["old_err"]:
                f.write(f"  OLD ERR: {entry['old_err']}\n")
            else:
                f.write(f"  OLD: {entry['old_out']}\n")
            if entry["new_err"]:
                f.write(f"  NEW ERR: {entry['new_err']}\n")
            else:
                f.write(f"  NEW: {entry['new_out']}\n")
            if entry["note"]:
                f.write(f"  NOTE: {entry['note']}\n")

    print(f"\nResults: {passed}/{total} passed ({passed / (passed + softfailed + failed) * 100:.1f}% of testable ({(passed + softfailed) / (passed + softfailed + failed) * 100:.1f}% incl. softfails)")
    print(f"Failures: {failed} | Soft failures: {softfailed} | Skipped: {skipped}")
    if timed_cases > 0:
        print(
            "Speed benchmark (non-timeout cases): "
            f"old total={old_total_time:.3f}s ({old_total_time / timed_cases * 1000:.3f}ms/case), "
            f"new total={new_total_time:.3f}s ({new_total_time / timed_cases * 1000:.3f}ms/case), "
            f"new tokenize={new_tokenize_time:.3f}s, new parse={new_parse_time:.3f}s, new execute={new_execute_time:.3f}s"
        )
        if new_total_time > 0:
            print(f"Relative speed (old/new total): {old_total_time / new_total_time:.3f}x")
    print(f"Log written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
