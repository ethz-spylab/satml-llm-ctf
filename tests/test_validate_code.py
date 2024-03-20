import pytest

from app.internals.code_exec import CodeCheckError, validate_code


def test_code_checker_correct_lambda():
    code = "f = lambda x: x"
    validate_code(code)


def test_code_checker_correct_function():
    code = "def f(x): return x"
    validate_code(code)


def test_code_checker_wrong_name():
    code = "g = lambda x: x"
    with pytest.raises(CodeCheckError) as exc_info:
        validate_code(code)
    assert "Please name your function" in str(exc_info.value)


def test_code_checker_wrong_not_only_f():
    code = "f = lambda x: x; print('Hello world!')"
    with pytest.raises(CodeCheckError) as exc_info:
        validate_code(code)
    assert "Please only submit a function." in str(exc_info.value)


def test_code_checker_wrong_no_function():
    code = "print('Hello world!')"
    with pytest.raises(CodeCheckError) as exc_info:
        validate_code(code)
    assert "Please only submit a function." in str(exc_info.value)


def test_code_checker_wrong_no_string_input():
    code = """
def f(x):
    assert isinstance(x, int)
    return x
"""
    with pytest.raises(CodeCheckError) as exc_info:
        validate_code(code)
    assert "Your function does not work with a string as an argument." in str(exc_info.value)
