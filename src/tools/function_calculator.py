import subprocess
import sys
import os
import tempfile
from typing import Dict, Any, Union

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

def calculate_formula(user_script: str) -> Union[Any, str]:
    """Safely executes a user provided script with restricted built-ins and a time limit.

    Args:
        user_script: The Python script provided by the user, optionally wrapped with ```python and ``` markers

    This function executes the provided script in a sandbox environment and returns
    the raw result value, or an error message string if execution failed.
    """
    user_script = clean_user_script(user_script)

    sandbox_script = """
import math
import numpy as np
import datetime
import json
import sys

allowed_builtins = {
    'abs': abs, 'min': min, 'max': max, 'sum': sum, 'len': len, 'range': range,
    'math': math, 'np': np, 'numpy': np, 'datetime': datetime, '__import__': __import__
}

globals_dict = {'__builtins__': {}}
globals_dict.update(allowed_builtins)

try:
    exec(user_code, globals_dict)
    result = globals_dict.get('result', None)
    if isinstance(result, np.ndarray):
        result = result.tolist()
    print(repr(result))
except Exception as e:
    print(f"ERROR: {str(e)}")
"""

    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as temp_file:
        temp_file.write(f"user_code = '''{user_script}'''\n{sandbox_script}".encode())
        temp_filename = temp_file.name

    try:
        env = os.environ.copy()
        env['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'
        process = subprocess.Popen(
            [sys.executable, temp_filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        try:
            stdout, stderr = process.communicate(timeout=2)
            if stderr and not any(warning in stderr for warning in ["Debugger warning:", "frozen modules", "PYDEVD_DISABLE_FILE_VALIDATION", "Set PYDEVD_DISABLE_FILE_VALIDATION=1"]):
                return format_output(user_script, f"Execution error: {stderr}")
            if stdout.startswith("ERROR: "):
                return format_output(user_script, stdout)
            try:
                return format_output(user_script, eval(stdout))
            except:
                return format_output(user_script, f"Invalid output format: {stdout}")
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return format_output(user_script, "Execution timed out (2 seconds limit)")
    finally:
        try:
            os.unlink(temp_filename)
        except:
            pass

if __name__ == "__main__":

    formula = """
    x = np.linspace(-5, 5, 100)
    y = np.sin(x) + np.cos(2*x)
    result = y
    """

    result = calculate_formula(formula)
    print(result)
