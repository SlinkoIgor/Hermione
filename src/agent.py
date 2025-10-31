from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode
from src.tools.function_calculator import calculate_formula
from src.tools.tz_convertor import convert_time, get_current_time, get_shifted_time
from src.tools.llm_tools import translate_text, fix_text, text_summarization, generate_bash_command
from src.tools.currency_converter import convert_currency
from src.llm_providers import get_openai_llm, get_litellm_llm
from textwrap import dedent
from typing import Dict, Any, List, Annotated, Literal
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
import logging
import time
import functools

logger = logging.getLogger(__name__)

_timing_data = []

def timed_node(node_name):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(state):
            start_time = time.time()
            try:
                result = func(state)
                elapsed = time.time() - start_time
                _timing_data.append({
                    "node": node_name,
                    "time": elapsed,
                    "timestamp": time.time()
                })
                logger.info(f"[TIMING] {node_name}: {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                _timing_data.append({
                    "node": node_name,
                    "time": elapsed,
                    "error": str(e),
                    "timestamp": time.time()
                })
                logger.error(f"[TIMING] {node_name} FAILED after {elapsed:.3f}s: {e}")
                raise
        return wrapper
    return decorator

def get_timing_data():
    return _timing_data.copy()

def clear_timing_data():
    global _timing_data
    _timing_data = []


time_zone_prompt = dedent("""
    You are a timezone converter. You don't chat. You need to handle timezone-related queries and produce a response in {query_language}.

    #Below are the examples how to solve the task:

    1. Current time queries:
    **Query:** "What time is it in Paris?"
    **Answer:** "Current time in Paris is 14:30"
    (use get_current_time function)

    2. Time shift queries:
    **Query:** "What time will it be in Tokyo in 3 hours?"
    **Answer:** "Current time in Tokyo is 14:30, in 3 hours it will be 17:30"
    (use get_shifted_time function)

    3. Time conversion queries:
    **Query:** "If it's 10 AM in New York, what time is it in London?"
    **Answer:** "10:00 AM in New York == 15:00 in London"
    (use convert_time function)

    4. Russian natural language time queries:
    **Query:** "давай встретимся в 3 дня по Барселоне"
    **Answer:** "3 дня по Барселоне == 16:00 по Никосии"
    (use convert_time function, where the second timezone is the current location)

    **RETURN ONLY THE ANSWER, NO OTHER TEXT.**

    To generate the answer, you need to:
    1. Determine which function(s) to use based on the query:
       - get_current_time: for current time queries
       - get_shifted_time: for time shift queries
       - convert_time: for time conversion between zones
    2. Convert location names to correct timezone format (e.g. "Europe/Berlin", "America/New_York")
    3. Call the appropriate function(s) with correct arguments
    4. Construct the answer from the result(s)
    5. For meeting time queries, the answer should be in the format: '<input time/phrase> == <converted time> по <current location> [local time]'
    6. IMPORTANT: The answer MUST be in {query_language}

    YOU MUST CALL THE TOOL!!!
    YOU MUST CALL THE TOOL!!!
    """)

math_formula_calculation_prompt = dedent("""
    To generate the answer, you need to:
    Write a python code that calculates the formula.
    You are allowed to use the following safe built-ins: abs, min, max, sum, len, range, round, int,
    float, bool, all, any, enumerate, zip, sorted, reversed, list, tuple, set, dict, math, numpy, datetime

    VERY IMPORTANT: put the result in a variable called "result"

    Below is an example how to solve the task:

    **Query:** "- (1/N) * SUM ( y_true * log(y_pred) ) where N=5 and y_true=[0,0,0,0,0] and y_pred=[0.1,0.2,0.3,0.4,0.5]"
    **Answer:**
    ```python
    import numpy as np

    N = 5
    y_true = [0, 0, 0, 0, 0]
    y_pred = [0.1, 0.2, 0.3, 0.4, 0.5]

    result = -(1/N) * sum(y_true[i] * np.log(y_pred[i]) for i in range(len(y_true)))
    ```

    **RETURN ONLY THE ANSWER, NO OTHER TEXT.**
    """)

currency_conversion_prompt = dedent("""
    #Below are the examples how to solve the task:

    **Query:** "How much is 100 USD in EUR?"
    **Tool call:** convert_currency(amount=100, source_currency="USD", target_currency="EUR")

    **Query:** "Convert 50 EUR to USD"
    **Tool call:** convert_currency(amount=50, source_currency="EUR", target_currency="USD")

    **Query:** "What is 200 RUB?"
    **Tool call:** convert_currency(amount=200, source_currency="RUB", target_currency="{native_currency}")

    To generate the answer, you need to:
    1. Extract the amount and currency codes from the query
    2. Call convert_currency tool with the correct arguments
    3. Use {native_currency} as target_currency ONLY if the target currency is not specified in the query

    YOU MUST CALL THE TOOL!!!
    YOU MUST CALL THE TOOL!!!
    """)

router_prompt = dedent("""
    Analyze the user input and determine which tasks it belongs to. Multiple tasks can be relevant for a single input.

    Possible tasks:
    1. math_formula_calculation - If the input has a math formula
    2. text_task - all other cases

    In cases when you doubt whether to include a task in the list – it's better to include it.

    Also figure out the query language and if the user input is in the native language ({native_language})

    Return ONLY the task names is_native_language and query_language as a string with comma delimiters, nothing else.

    Return format: "task1,task2,...,taskN,query_language,is_native_language"
    Example: "text_task,Spanish,False"

    The one to the last part (query_language) should be the query language.
    The last part (is_native_language) should be "True" if the user input is in {native_language} or "False" otherwise.
    """)

def merge_tool_warning(a: bool, b: bool) -> bool:
    return a or b

class AgentState(MessagesState):
    tasks: List[str]
    is_native_language: bool
    query_language: str
    tool_warning: Annotated[bool, merge_tool_warning] = False
    out_tz_conversion: str = ""
    out_math_result: str = ""
    out_math_script: str = ""
    out_currency_conversion: str = ""
    out_bash_command: str = ""
    out_translation: str = ""
    out_fixed: str = ""
    out_tldr: str = ""
    out_text: str = ""


class AgentBuilder:
    def __init__(
        self,
        native_language: str = "Русский",
        target_language: str = "English",
        native_currency: str = "EUR",
        current_location: str = "Asia/Nicosia",
        base_model: str = "gpt-5",
        fast_model: str = "gpt-5-mini",
        temperature: float = 1,
        provider: Literal["openai", "litellm"] = "openai",
        thinking_budget: int = None,
    ):
        self.native_language = native_language
        self.target_language = target_language
        self.native_currency = native_currency
        self.current_location = current_location
        self.base_model = base_model
        self.fast_model = fast_model
        self.temperature = temperature
        self.provider = provider
        self.thinking_budget = thinking_budget

    def _get_llm(self, use_fast: bool = False) -> ChatOpenAI:
        model_name = self.fast_model if use_fast else self.base_model
        if self.provider == "litellm":
            return get_litellm_llm(model_name, self.temperature, self.thinking_budget)
        else:
            return get_openai_llm(model_name, self.temperature, self.thinking_budget)

    def invoke_llm_with_tools(
        self,
        tools: List[BaseTool],
        system_message: SystemMessage,
        user_message: HumanMessage,
        check_tool_calls: bool = True,
        use_fast: bool = False
    ) -> Dict[str, Any]:
        llm = self._get_llm(use_fast=use_fast).bind_tools(tools, parallel_tool_calls=False)
        response = llm.invoke([system_message, user_message])

        if check_tool_calls and not any(hasattr(msg, 'tool_calls') and msg.tool_calls for msg in [response]):
            logger.warning("Tool wasn't called in the response")
            return {"messages": [system_message, response], "tool_warning": True}

        return {"messages": [system_message, response], "tool_warning": False}

    def build(self) -> Any:

        @timed_node("task_router_node")
        def task_router_node(state: AgentState) -> Dict[str, Any]:
            router_llm = self._get_llm(use_fast=True)
            task_message = SystemMessage(router_prompt.format(native_language=self.native_language))
            user_message = state["messages"][0]
            user_content = user_message.content[:200] if hasattr(user_message, "content") and user_message.content else ""
            task_response = router_llm.invoke([task_message, HumanMessage(content=user_content)])
            parts = task_response.content.lower().split(",")
            if "text_task" not in parts:
                parts = ["text_task"] + parts
            task_names = [task.strip() for task in parts[:-2]]
            print(parts[-1])
            query_language = parts[-2].strip()
            is_native_language = parts[-1].strip() == "true"

            print("is_native_language", is_native_language, "query_language", query_language, "native_language", self.native_language)

            return {"tasks": task_names,
                    "is_native_language": is_native_language,
                    "query_language": query_language,
                    "out_text": user_message.content}

        def routing_function(state: AgentState) -> list[str]:
            routes = []
            for task in state["tasks"]:
                if task == "text_task":
                    if len(state["messages"][0].content.split()) > 100:
                        routes.append("text_summarization_node")
                    routes.append("text_translation_node")
                    routes.append("text_fix_node")
                elif task == "math_formula_calculation":
                    routes.append(f"{task}_node")
                # elif task == "tz_conversion":
                #     routes.append(f"{task}_node")
                # elif task == "currency_conversion":
                #     routes.append(f"{task}_node")
                # elif task == "bash_command":
                #     routes.append(f"{task}_node")
            return routes

        @timed_node("text_translation_node")
        def text_translation_node(state: AgentState) -> Dict[str, Any]:
            translated_text = translate_text(
                text=state["messages"][0].content,
                native_language=self.native_language,
                target_language=self.target_language,
                is_native_language=state["is_native_language"],
            )
            return {"out_translation": translated_text}

        @timed_node("text_fix_node")
        def text_fix_node(state: AgentState) -> Dict[str, Any]:
            fixed_text = fix_text(
                text=state["messages"][0].content
            )
            return {"out_fixed": fixed_text}

        @timed_node("text_summarization_node")
        def text_summarization_node(state: AgentState) -> Dict[str, Any]:
            return {"out_tldr": text_summarization(
                text=state["messages"][0].content,
                native_language=self.native_language)}

        @timed_node("tz_conversion_node")
        def tz_conversion_node(state: AgentState) -> Dict[str, Any]:
            system_msg = SystemMessage(
                time_zone_prompt.format(current_location=self.current_location, query_language=state["query_language"]))
            return self.invoke_llm_with_tools(
                tools=[convert_time, get_current_time, get_shifted_time],
                system_message=system_msg,
                user_message=state["messages"][0]
            )

        @timed_node("tz_conversion_outro_node")
        def tz_conversion_outro_node(state: AgentState) -> Dict[str, Any]:
            tz_conversion_llm = self._get_llm(use_fast=True)
            response = tz_conversion_llm.invoke(state["messages"])
            return {"out_tz_conversion": response.content}

        @timed_node("math_formula_calculation_node")
        def math_formula_calculation_node(state: AgentState) -> Dict[str, Any]:
            math_formula_calculation_llm = self._get_llm(use_fast=True)
            response = math_formula_calculation_llm.invoke([SystemMessage(math_formula_calculation_prompt), state["messages"][0]])
            calculation_result = calculate_formula(response.content)
            return {
                "out_math_result": str(calculation_result),
                "out_math_script": response.content
            }

        @timed_node("currency_conversion_node")
        def currency_conversion_node(state: AgentState) -> Dict[str, Any]:
            system_msg = SystemMessage(
                currency_conversion_prompt.format(native_currency=self.native_currency))
            return self.invoke_llm_with_tools(
                tools=[convert_currency],
                system_message=system_msg,
                user_message=state["messages"][0]
            )

        @timed_node("currency_conversion_outro_node")
        def currency_conversion_outro_node(state: AgentState) -> Dict[str, Any]:
            last_message = state["messages"][-1]
            result = ""

            if hasattr(last_message, 'content'):
                try:
                    import ast
                    result_dict = ast.literal_eval(last_message.content)

                    conversion_result = result_dict.get('result')
                    amount = result_dict.get('amount', 0)
                    source_currency = result_dict.get('source_currency', '')
                    target_currency = result_dict.get('target_currency', '')

                    if conversion_result is not None:
                        result = f"{amount} {source_currency} == {conversion_result:.2f} {target_currency}"
                    else:
                        error_msg = result_dict.get('error', 'Unknown error')
                        result = f"Error: {error_msg}"
                except (ValueError, SyntaxError):
                    result = "Error: Could not parse currency conversion result"
            else:
                result = "Error: Could not extract currency conversion result"

            return {"messages": [AIMessage("")], "out_currency_conversion": result}

        @timed_node("bash_command_node")
        def bash_command_node(state: AgentState) -> Dict[str, Any]:
            bash_command = generate_bash_command(state["messages"][0].content)
            return {"out_bash_command": bash_command}

        builder = StateGraph(AgentState)

        builder.add_node(task_router_node)
        builder.add_node(text_translation_node)
        builder.add_node(text_fix_node)
        builder.add_node(text_summarization_node)
        builder.add_node(tz_conversion_node)
        builder.add_node(math_formula_calculation_node)
        builder.add_node(currency_conversion_node)
        builder.add_node(currency_conversion_outro_node)
        builder.add_node(bash_command_node)

        builder.add_node(ToolNode(tools=[convert_time], name="tz_conversion_tool_node"))
        builder.add_node(tz_conversion_outro_node)
        builder.add_node(ToolNode(tools=[convert_currency], name="currency_conversion_tool_node"))

        builder.add_edge(START, "task_router_node")
        builder.add_conditional_edges("task_router_node", routing_function)

        builder.add_edge("text_translation_node", END)
        builder.add_edge("text_fix_node", END)
        builder.add_edge("text_summarization_node", END)

        builder.add_edge("tz_conversion_node", "tz_conversion_tool_node")
        builder.add_edge("tz_conversion_tool_node", "tz_conversion_outro_node")
        builder.add_edge("tz_conversion_outro_node", END)

        builder.add_edge("math_formula_calculation_node", END)

        builder.add_edge("currency_conversion_node", "currency_conversion_tool_node")
        builder.add_edge("currency_conversion_tool_node", "currency_conversion_outro_node")
        builder.add_edge("currency_conversion_outro_node", END)

        builder.add_edge("bash_command_node", END)

        return builder.compile()


if __name__ == "__main__":
    agent = AgentBuilder(native_currency="EUR").build()
