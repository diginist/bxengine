import pytest

from bxengine.runtime.executor import Executor, ExecutorResult
from bxengine.runtime.extensions.builtin import BuiltinExtension
from bxengine.runtime.extensions.BxeExtension import (
    BxeStatefulExtension,
    BxeStatelessExtension,
    GlobalVariableBppExtension,
    MyBxeExtension,
    bpp_function,
)
from bxengine.runtime.context import RuntimeContext
from bxengine.parsing.nodes import Node, Nodes
from bxengine.spans import SpanData
from bxengine.exceptions import BxeRuntimeException

from conftest import run_program, run_program_raw


class AliasExtension(BxeStatelessExtension):
    @staticmethod
    @bpp_function(name="ALIASBASE", aliases=["AB", "alias_base"])
    def alias_target() -> str:
        return "alias-ok"


# =====================================================================
# Outer text
# =====================================================================

class TestOuterText:
    def test_plain_text(self):
        assert run_program("just plain text") == "just plain text"

    def test_empty_input(self):
        assert run_program("") == ""

    def test_text_around_function(self):
        assert run_program("Hello [CONCAT \"world\" \"!\"] end") == "Hello world! end"


# =====================================================================
# Control flow
# =====================================================================

class TestControlFlow:
    def test_if_true(self):
        assert run_program('[IF 1 "yes" "no"]') == "yes"

    def test_if_false(self):
        assert run_program('[IF 0 "yes" "no"]') == "no"

    def test_if_truthy_string(self):
        assert run_program('[IF "anything" "yes" "no"]') == "yes"

    def test_if_empty_string_is_falsy(self):
        assert run_program('[IF "" "yes" "no"]') == "no"

    def test_if_no_else(self):
        assert run_program('[IF 0 "yes"]') == ""

    def test_if_lazy_eval_condition_true(self):
        assert run_program('[IF 1 [DEFINE x "taken"] [DEFINE x "skipped"]] [VAR x]') == " taken"

    def test_if_lazy_eval_condition_false(self):
        assert run_program('[IF 0 [DEFINE x "skipped"] [DEFINE x "taken"]] [VAR x]') == " taken"

    def test_compare_gt(self):
        assert run_program('[COMPARE 5 ">" 3]') == "1"
        assert run_program('[COMPARE 3 ">" 5]') == "0"

    def test_compare_lt(self):
        assert run_program('[COMPARE 3 "<" 5]') == "1"

    def test_compare_eq(self):
        assert run_program('[COMPARE 5 "=" 5]') == "1"
        assert run_program('[COMPARE 5 "==" 5]') == "1"

    def test_compare_neq(self):
        assert run_program('[COMPARE 5 "!=" 3]') == "1"

    def test_compare_gte(self):
        assert run_program('[COMPARE 5 ">=" 5]') == "1"
        assert run_program('[COMPARE 5 ">=" 3]') == "1"

    def test_compare_lte(self):
        assert run_program('[COMPARE 3 "<=" 5]') == "1"

    def test_compare_and(self):
        assert run_program('[COMPARE 1 "and" 1]') == "1.0"
        assert run_program('[COMPARE 1 "and" 0]') == "0.0"

    def test_compare_or(self):
        assert run_program('[COMPARE 0 "or" 1]') == "1.0"
        assert run_program('[COMPARE 0 "or" 0]') == "0.0"

    def test_compare_type_mismatch_raises(self):
        res = run_program_raw('[COMPARE 5 ">" "three"]')
        assert isinstance(res, ExecutorResult.Error)
        assert isinstance(res.exception, TypeError)

    def test_compare_invalid_operator(self):
        res = run_program_raw('[COMPARE 5 "~" 3]')
        assert isinstance(res, ExecutorResult.Error)

    def test_throw(self):
        res = run_program_raw('[THROW "boom"]')
        assert isinstance(res, ExecutorResult.Error)
        assert "boom" in str(res.exception)

    def test_comment(self):
        assert run_program('[# this is a comment]visible') == "visible"

    def test_nested_if(self):
        assert run_program('[IF [COMPARE 5 ">" 3] "bigger" "smaller"]') == "bigger"


# =====================================================================
# Variables
# =====================================================================

class TestVariables:
    def test_define_and_var(self):
        assert run_program('[DEFINE x 42] [VAR x]') == " 42"

    def test_define_string(self):
        assert run_program('[DEFINE name "Alice"] [VAR name]') == " Alice"

    def test_var_undefined_raises(self):
        res = run_program_raw("[VAR nonexistent]")
        assert isinstance(res, ExecutorResult.Error)
        assert isinstance(res.exception, NameError)

    def test_define_invalid_name(self):
        res = run_program_raw('[DEFINE "123bad" 1]')
        assert isinstance(res, ExecutorResult.Error)

    def test_define_overwrite(self):
        assert run_program('[DEFINE x 1] [DEFINE x 2] [VAR x]') == "  2"


# =====================================================================
# Args
# =====================================================================

class TestArgs:
    def test_args_by_index(self):
        assert run_program("[ARGS 0] [ARGS 1]", program_args=["hello", "world"]) == "hello world"

    def test_args_all(self):
        assert run_program("[ARGS]", program_args=["a", "b", "c"]) == '[ARRAY "a" "b" "c"]'

    def test_args_out_of_range(self):
        assert run_program("[ARGS 5]", program_args=["only-one"]) == ""

    def test_args_no_args(self):
        assert run_program("[ARGS]") == "[ARRAY ]"


# =====================================================================
# Math
# =====================================================================

class TestMath:
    def test_basic_addition(self):
        assert run_program("[MATH 2 + 3]") == "5"

    def test_operator_precedence(self):
        assert run_program("[MATH 2 + 3 * 4]") == "14"

    def test_exponent(self):
        assert run_program("[MATH 2 ^ 10]") == "1024"

    def test_division(self):
        assert run_program("[MATH 10 / 3]") == "3.3333333333333335"

    def test_modulo(self):
        assert run_program("[MATH 10 % 3]") == "1"

    def test_subtraction(self):
        assert run_program("[MATH 10 - 3]") == "7"

    def test_float_arithmetic(self):
        assert run_program("[MATH 3 + 4.5]") == "7.5"

    def test_nested_functions_in_math(self):
        assert run_program("[MATH [ABS -3] + [ROUND 2.7]]") == "6"

    def test_division_by_zero(self):
        res = run_program_raw("[MATH 1 / 0]")
        assert isinstance(res, ExecutorResult.Error)
        assert isinstance(res.exception, ZeroDivisionError)

    def test_randint(self):
        for _ in range(20):
            val = int(run_program("[RANDINT 1 10]"))
            assert 1 <= val <= 10

    def test_random(self):
        val = float(run_program("[RANDOM 0.0 1.0]"))
        assert 0.0 <= val <= 1.0

    def test_floor(self):
        assert run_program("[FLOOR 3.7]") == "3"
        assert run_program("[FLOOR -1.2]") == "-2"

    def test_ceil(self):
        assert run_program("[CEIL 3.2]") == "4"
        assert run_program("[CEIL -1.7]") == "-1"

    def test_round(self):
        assert run_program("[ROUND 3.7]") == "4"
        assert run_program("[ROUND 3.456 2]") == "3.46"

    def test_abs(self):
        assert run_program("[ABS -5]") == "5"
        assert run_program("[ABS 5]") == "5"

    def test_abs_type_error(self):
        res = run_program_raw('[ABS "hello"]')
        assert isinstance(res, ExecutorResult.Error)
        assert isinstance(res.exception, ValueError)

    def test_mod(self):
        assert run_program("[MOD 10 3]") == "1"

    def test_mod_by_zero(self):
        res = run_program_raw("[MOD 10 0]")
        assert isinstance(res, ExecutorResult.Error)
        assert isinstance(res.exception, ZeroDivisionError)

    def test_log(self):
        assert run_program("[LOG 100 10]") == "2.0"

    def test_log_zero_base(self):
        res = run_program_raw("[LOG 100 0]")
        assert isinstance(res, ExecutorResult.Error)

    def test_factorial(self):
        assert run_program("[FACTORIAL 5]") == "120.0"

    def test_sin(self):
        assert run_program("[SIN 0]") == "0.0"

    def test_cos(self):
        assert run_program("[COS 0]") == "1.0"

    def test_tan(self):
        assert run_program("[TAN 0]") == "0.0"

    def test_min(self):
        assert run_program("[MIN [ARRAY 3 1 2]]") == "1.0"

    def test_max(self):
        assert run_program("[MAX [ARRAY 3 1 2]]") == "3.0"


# =====================================================================
# String functions
# =====================================================================

class TestString:
    def test_concat(self):
        assert run_program('[CONCAT "hello " "world"]') == "hello world"

    def test_concat_numbers(self):
        assert run_program('[CONCAT "val=" 42]') == "val=42"

    def test_split(self):
        assert run_program('[SPLIT "a,b,c" ","]') == '[ARRAY "a" "b" "c"]'

    def test_replace(self):
        assert run_program('[REPLACE "hello world" "world" "there"]') == "hello there"

    def test_length(self):
        assert run_program('[LENGTH "hello"]') == "5"

    def test_length_number(self):
        assert run_program("[LENGTH 12345]") == "5"

    def test_indexof_string(self):
        assert run_program('[INDEXOF "hello world" "world"]') == "6"

    def test_indexof_not_found(self):
        assert run_program('[INDEXOF "hello" "xyz"]') == ""

    def test_join(self):
        assert run_program('[JOIN [SPLIT "a,b,c" ","] "-"]') == "a-b-c"

    def test_setindex_string(self):
        assert run_program('[SETINDEX "hello" 0 "H"]') == "Hello"

    def test_char(self):
        assert run_program("[CHAR 65]") == "A"

    def test_unicode(self):
        assert run_program("[UNICODE A]") == "65"

    def test_choosechar(self):
        result = run_program('[CHOOSECHAR "abc"]')
        assert result in "abc"


# =====================================================================
# Array functions
# =====================================================================

class TestArray:
    def test_array(self):
        assert run_program("[ARRAY 1 2 3]") == '[ARRAY "1" "2" "3"]'

    def test_index(self):
        assert run_program("[INDEX [ARRAY a b c] 1]") == "b"

    def test_slice_string(self):
        assert run_program('[SLICE "hello world" 0 5]') == "hello"

    def test_slice_array(self):
        assert run_program("[SLICE [ARRAY a b c d] 1 3]") == '[ARRAY "b" "c"]'

    def test_shuffle(self):
        result = run_program("[SHUFFLE [ARRAY 1 2 3]]")
        assert "ARRAY" in result

    def test_sort(self):
        assert run_program("[SORT [ARRAY 3 1 2]]") == '[ARRAY "1.0" "2.0" "3.0"]'

    def test_choose(self):
        result = run_program("[CHOOSE [ARRAY 10 20 30]]")
        assert result in ("10", "20", "30")

    def test_concat_arrays(self):
        assert run_program("[CONCAT [ARRAY 1 2] [ARRAY 3 4]]") == '[ARRAY "1" "2" "3" "4"]'

    def test_repeat_array(self):
        assert run_program("[REPEAT [ARRAY 1 2] 2]") == '[ARRAY "1" "2" "1" "2"]'


# =====================================================================
# Utility
# =====================================================================

class TestUtility:
    def test_repeat_string(self):
        assert run_program('[REPEAT "ab" 3]') == "ababab"

    def test_repeat_limit(self):
        res = run_program_raw("[REPEAT x 9999]")
        assert isinstance(res, ExecutorResult.Error)
        assert isinstance(res.exception, ValueError)

    def test_type_int(self):
        assert run_program("[TYPE 42]") == "int"

    def test_type_float(self):
        assert run_program("[TYPE 3.14]") == "float"

    def test_type_string(self):
        assert run_program('[TYPE "hi"]') == "str"

    def test_type_list(self):
        assert run_program("[TYPE [ARRAY 1]]") == "list"

    def test_time(self):
        val = float(run_program("[TIME]"))
        assert val > 0


# =====================================================================
# Extensions
# =====================================================================

class TestExtensions:
    def test_stateless_extension(self):
        exts = [BuiltinExtension(), MyBxeExtension()]
        assert run_program("[test_basic]", extensions=exts) == "1"

    def test_stateless_args(self):
        exts = [BuiltinExtension(), MyBxeExtension()]
        assert run_program("[test_args 5]", extensions=exts) == "10"

    def test_stateless_float_coercion(self):
        exts = [BuiltinExtension(), MyBxeExtension()]
        assert run_program("[test_argsfloat 2.5]", extensions=exts) == "5.0"

    def test_stateless_int_to_float_coercion(self):
        exts = [BuiltinExtension(), MyBxeExtension()]
        assert run_program("[test_argsfloat 3]", extensions=exts) == "6.0"

    def test_node_transformer_extension(self):
        exts = [BuiltinExtension(), MyBxeExtension()]
        assert run_program("[test_nodetransform]", extensions=exts) == "1"

    def test_function_alias_primary_name(self):
        exts = [BuiltinExtension(), AliasExtension()]
        assert run_program("[ALIASBASE]", extensions=exts) == "alias-ok"

    def test_function_alias_short_alias(self):
        exts = [BuiltinExtension(), AliasExtension()]
        assert run_program("[AB]", extensions=exts) == "alias-ok"

    def test_function_alias_case_insensitive_alias(self):
        exts = [BuiltinExtension(), AliasExtension()]
        assert run_program("[alias_base]", extensions=exts) == "alias-ok"

    def test_global_variable_extension(self):
        assert (
            run_program(
                '[GLOBAL DEFINE x 42] [GLOBAL VAR x]',
                stateful_extensions=[GlobalVariableBppExtension],
            ).strip()
            == "42"
        )

    def test_stateful_isolation_between_executions(self):
        exe = Executor(
            extensions=[BuiltinExtension()],
            stateful_extensions=[GlobalVariableBppExtension],
        )
        from bxengine.tokenizer.tokenize import Tokenizer
        from bxengine.parsing.parser import Parser

        tok1 = Tokenizer.tokenize('[GLOBAL DEFINE x 99]')
        par1 = Parser.parse('[GLOBAL DEFINE x 99]', tok1.tokens)
        r1 = exe.execute(par1.nodes)
        assert isinstance(r1, ExecutorResult.Success)

        tok2 = Tokenizer.tokenize("[GLOBAL VAR x]")
        par2 = Parser.parse("[GLOBAL VAR x]", tok2.tokens)
        r2 = exe.execute(par2.nodes)
        assert isinstance(r2, ExecutorResult.Error)

    def test_stateful_exposed_on_result(self):
        exe = Executor(
            extensions=[BuiltinExtension()],
            stateful_extensions=[GlobalVariableBppExtension],
        )
        from bxengine.tokenizer.tokenize import Tokenizer
        from bxengine.parsing.parser import Parser

        tok = Tokenizer.tokenize('[GLOBAL DEFINE name "Alice"]')
        par = Parser.parse('[GLOBAL DEFINE name "Alice"]', tok.tokens)
        result = exe.execute(par.nodes)
        assert isinstance(result, ExecutorResult.Success)
        gv_exts = [e for e in result.stateful_extensions if isinstance(e, GlobalVariableBppExtension)]
        assert len(gv_exts) == 1
        assert gv_exts[0].global_variables == {"name": "Alice"}


# =====================================================================
# Error handling
# =====================================================================

class TestErrors:
    def test_undefined_function(self):
        res = run_program_raw("[NOSUCHFUNC 1]")
        assert isinstance(res, ExecutorResult.Error)
        assert isinstance(res.exception, NameError)

    def test_type_error_propagates(self):
        res = run_program_raw('[ABS "hello"]')
        assert isinstance(res, ExecutorResult.Error)
        assert isinstance(res.exception, ValueError)

    def test_unclosed_bracket(self):
        # BPPCOMPAT: unclosed brackets at EOF are auto-closed by parser
        from bxengine.tokenizer.tokenize import Tokenizer, TokenizationResult
        from bxengine.parsing.parser import Parser, ParsingResult

        tok = Tokenizer.tokenize("[FUNC")
        assert isinstance(tok, TokenizationResult.Success)
        par = Parser.parse("[FUNC", tok.tokens)
        assert isinstance(par, ParsingResult.Success)

    def test_tokenize_unclosed_string_at_top_level(self):
        # Top-level unclosed quotes get absorbed as outer text (BPPCOMPAT)
        from bxengine.tokenizer.tokenize import Tokenizer, TokenizationResult

        res = Tokenizer.tokenize('"unclosed')
        assert isinstance(res, TokenizationResult.Success)
