from typing import Any
import math
import numpy as np
import signal
import contextlib

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

class TimeoutException(Exception):
    pass

@contextlib.contextmanager
def timeout(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Execution timed out")

    # Set the signal handler and a 1-second alarm
    original_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Restore the original signal handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)

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
        # Execute the code in the safe environment with a 1-second timeout
        local_vars = {}
        with timeout(1):
            exec(code, safe_globals, local_vars)

        # Return the result if it exists
        if 'result' in local_vars:
            return local_vars['result']
        else:
            return "No result variable found in the code."
    except TimeoutException:
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
