from typing import Any
import math
import numpy as np

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

def format_output(script: str, result: Any) -> str:
    return f"=======<result>=======\n{result}\n\n=====<script>======\n{script}"

def calculate_formula(code: str) -> Any:
    """Executes the provided Python code and returns the result.

    Parameters:
        code: A string containing Python code to execute

    Returns:
        The result of executing the code
    """
    # Create a safe local environment with only allowed modules
    safe_globals = {
        # Math module and its functions
        'math': math,
        'sqrt': math.sqrt,
        'pow': math.pow,
        'exp': math.exp,
        'log': math.log,
        'log10': math.log10,
        'log2': math.log2,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'asin': math.asin,
        'acos': math.acos,
        'atan': math.atan,
        'sinh': math.sinh,
        'cosh': math.cosh,
        'tanh': math.tanh,
        'pi': math.pi,
        'e': math.e,
        'ceil': math.ceil,
        'floor': math.floor,
        'trunc': math.trunc,
        'factorial': math.factorial,
        'gcd': math.gcd,
        'lcm': math.lcm,

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

    # Execute the code in the safe environment
    local_vars = {}
    exec(code, safe_globals, local_vars)

    # Return the result if it exists
    if 'result' in local_vars:
        return local_vars['result']
    else:
        return "No result variable found in the code."

if __name__ == "__main__":

    formula = """
    x = np.linspace(-5, 5, 100)
    y = np.sin(x) + np.cos(2*x)
    result = y
    """

    result = calculate_formula(formula)
    print(result)
