from bxengine.runtime.executor import ExecutorResult

from conftest import run_program, run_program_raw


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
