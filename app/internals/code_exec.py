import ast

from wasm_exec import WasmExecError, WasmExecutor


class CodeCheckError(Exception):
    pass


PYTHON_FILTER_FUNCTION_NAME = "f"


def execute_function(
    code: str, chat_history: list[str], input: str, secret: str, function_name: str = PYTHON_FILTER_FUNCTION_NAME
) -> str:
    wasm_executor = WasmExecutor(use_fuel=True, fuel=40_000_000_000)
    code_to_execute = f"""
{code}
print({function_name}(chat_history, input, secret))
"""
    result = wasm_executor.exec(
        code_to_execute.replace("\\", r"\\"), locals={"chat_history": chat_history, "input": input, "secret": secret}
    ).text
    return result


def validate_code(code: str) -> None:
    tree = ast.parse(code)
    if len(tree.body) != 1:
        raise CodeCheckError("Please only submit a function and no other code.")
    if not (
        isinstance(tree.body[0], ast.FunctionDef)
        or (isinstance(tree.body[0], ast.Assign) and isinstance(tree.body[0].value, ast.Lambda))
    ):
        raise CodeCheckError("Please only submit a function.")

    if isinstance(tree.body[0], ast.FunctionDef):
        function = tree.body[0]
        function_name = function.name

    else:
        assert isinstance(tree.body[0].targets[0], ast.Name)
        function_name = tree.body[0].targets[0].id

    if function_name != PYTHON_FILTER_FUNCTION_NAME:
        raise CodeCheckError(f"Please name your function `{PYTHON_FILTER_FUNCTION_NAME}` instead of `{function_name}`.")
    try:
        result = execute_function(code, ["test", "test"], "test" * 100, "123456")
    except WasmExecError as e:
        print(e)
        raise CodeCheckError("Does not work as expected. Double-check it.")
    except TimeoutError:
        raise CodeCheckError("Your function takes too long to execute. Double-check it.")

    if not isinstance(result, str):
        raise CodeCheckError("Your function does not return a string. Double-check it.")
