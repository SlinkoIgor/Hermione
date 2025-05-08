from typing import Any
import math
import numpy as np
from concurrent.futures import ThreadPoolExecutor, TimeoutError

def clean_user_script(user_script: str) -> str:
    """Cleans the user script by removing code block markers and import statements.

    Args:
        user_script: The Python script provided by the user

    Returns:
        Cleaned script without code block markers and import statements
    """
    script = user_script.strip()

    if script.startswith("```python") and script.endswith("```"):
        script = script[len("```python"):].lstrip()
        script = script[:-3].rstrip()

    lines = script.split('\n')
    cleaned_lines = [line for line in lines if not (line.strip().startswith(('import ', 'from ')) and ' import ' in line.strip())]

    return '\n'.join(cleaned_lines)

def execute_code(code: str, safe_globals: dict) -> Any:
    local_vars = {}
    exec(code, safe_globals, local_vars)
    return local_vars.get('result', "No result variable found in the code.")

def calculate_formula(code: str) -> Any:
    """Executes the provided Python code and returns the result.

    Parameters:
        code: A string containing Python code to execute

    Returns:
        The result of executing the code
    """
    code = clean_user_script(code)

    # Create a safe local environment with only allowed modules
    safe_globals = {
        # Math module and its functions
        'math': math,

        # NumPy module
        'np': np,
        'numpy': np,

        # Built-in functions
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'len': len,
        'range': range,
        'round': round,
        'int': int,
        'float': float,
        'bool': bool,
        'all': all,
        'any': any,
        'enumerate': enumerate,
        'zip': zip,
        'sorted': sorted,
        'reversed': reversed,
        'list': list,
        'tuple': tuple,
        'set': set,
        'dict': dict,
    }

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(execute_code, code, safe_globals)
            result = future.result(timeout=1)
            return result
    except TimeoutError:
        return "Execution timed out after 1 second."
    except Exception as e:
        return f"Error executing code: {str(e)}"

if __name__ == "__main__":

    formula = """
    x = np.linspace(-5, 5, 100)
    y = np.sin(x) + np.cos(2*x)
    result = y
    """

    result = calculate_formula(formula)
    print(result)
