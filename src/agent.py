from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode
from src.tools.function_calculator import calculate_formula
from src.tools.tz_convertor import convert_time
from src.tools.llm_tools import translate_text, fix_text, text_summarization, generate_bash_command
from src.tools.currency_converter import convert_currency
from textwrap import dedent
from typing import Dict, Any, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)


time_zone_prompt = dedent("""
    You are a tz converter. You don't chat. You need to make a time zone conversion and produce a response in {query_language}.

    #Below are the examples how to solve the task:
    1. **Query:** "let's meet at H1H1:M1M1 [time_zone/location] time"
    **Answer:** "H1H1:M1M1 [time_zone/location] == H2H2:M2M2 [current_location]"

   In these conversation:
    - H1H1:M1M1 is time of some [time_zone] (e.g. CET, UTC+2) or [location] (e.g. Berlin)
    - H2H2:M2M2 is time of [current_location]
    - [current_location] is {current_location}

    2. **Query:** "давай встретимся в полночь по Берлину"
    **Answer:** "полночь по Берлину == 01:00 по Никосии"
    (in this toy example the current location is set to Nicosia)

    3. **Query:** "можем ли мы перенести встречу в 10 AM по NY на час вперед?"
    **Answer:** "10 AM по NY == 3 PM по Барселоне"
    (in this toy example the current location is set to Barcelona)

    4. **Query:** "Если в Берлине 10 AM, то в Париже"
    **Answer:** "10 AM в Берлину == 11 AM в Париже"

    5. **Query:** "Сколько сейчас в Париже?"
    **Answer:** "Сейчас в Лондоне 11:00, значит в Париже 12:00"
    (in this toy example the current location is set to London,
    the time_in arg is set None, so the current time is used)

    6. **Query:** "What will be the time in Paris in 2 hours?"
    **Answer:** "Current time in London is 11:00, so in Paris it's 12:00. In 2 hours Paris time will be 14:00"
    (in this toy example the current location is set to London,
    the time_in arg is set None, so the current time is used.
    The correct_time_zone can't do the time diff, so you trigger it with time_in=None, and then do the shift yourself)


    **RETURN ONLY THE ANSWER, NO OTHER TEXT.**

    To generate the answer, you need to:
    1. convert [time_zone/location] to the correct_time_zone in python format (e.g. "Europe/Berlin", "America/New_York")
    2. convert current_location which is {current_location} to the correct_current_time_zone in python format (e.g. "Europe/Berlin", "America/New_York")
    3. run a function convert_time with the correct arguments (H1H1:M1M1, correct_time_zone, correct_current_time_zone)
    4. construct the answer from the result of the convert_time function.
    5. IMPORTANT: The answer MUST be in {query_language}

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
    1. tz_conversion - If the input has information about time that doesn't match the current time zone
    2. math_formula_calculation - If the input has a math formula
    3. convert_currency - If the input has information about currency conversion
    4. bash_command - If the input contains an incorrect bash command or a natural language description of what the user wants to do with bash
    5. text_task - all other cases

    In cases when you doubt whether to include a task in the list – it's better to include it.

    Return format: task1,task2,...,taskN,is_native_language,query_language

    Return ONLY the task names and whether the text is in the native language ({native_language}) as a string with comma delimiters, nothing else.
    The last part should be "True" if the text is in {native_language} or "False" otherwise.
    Example: "text_task,tz_conversion,False,Spanish"
    """)


class AgentState(MessagesState):
    tasks: List[str]
    is_native_language: bool
    query_language: str
    tool_warning: bool = False
    out_tz_conversion: str = ""
    out_math_result: str = ""
    out_math_script: str = ""
    out_currency_conversion: str = ""
    out_bash_command: str = ""
    out_translation: str = ""
    out_fixed: str = ""
    out_tldr: str = ""


class AgentBuilder:
    def __init__(
        self,
        native_language: str = "Русский",
        target_language: str = "English",
        native_currency: str = "EUR",
        current_location: str = "Asia/Nicosia",
        model_name: str = "gpt-4o-mini",
        temperature: float = 0,
    ):
        self.native_language = native_language
        self.target_language = target_language
        self.native_currency = native_currency
        self.current_location = current_location
        self.model_name = model_name
        self.temperature = temperature

    def invoke_llm_with_tools(
        self,
        tools: List[BaseTool],
        system_message: SystemMessage,
        user_message: HumanMessage,
        check_tool_calls: bool = True
    ) -> Dict[str, Any]:
        llm = ChatOpenAI(model=self.model_name, temperature=self.temperature).bind_tools(
            tools, parallel_tool_calls=False)
        response = llm.invoke([system_message, user_message])

        if check_tool_calls and not any(hasattr(msg, 'tool_calls') and msg.tool_calls for msg in [response]):
            logger.warning("Tool wasn't called in the response")
            return {"messages": [system_message, response], "tool_warning": True}

        return {"messages": [system_message, response], "tool_warning": False}

    def build(self) -> Any:

        def task_router_node(state: AgentState) -> Dict[str, Any]:
            router_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)
            task_message = SystemMessage(router_prompt.format(native_language=self.native_language))
            user_message = state["messages"][0]
            user_content = user_message.content[:200] if hasattr(user_message, "content") and user_message.content else ""
            task_response = router_llm.invoke([task_message, HumanMessage(content=user_content)])
            parts = task_response.content.lower().split(",")
            task_names = [task.strip() for task in parts[:-2]]
            is_native_language = parts[-2].strip() == "true"
            query_language = parts[-1].strip()
            print(f"query_language: {query_language}")

            return {"tasks": task_names,
                    "is_native_language": is_native_language,
                    "query_language": query_language}

        def text_task_node(state: AgentState) -> Dict[str, Any]:
            return None

        def text_translation_node(state: AgentState) -> Dict[str, Any]:
            translated_text = translate_text(
                text=state["messages"][0].content,
                native_language=self.native_language,
                target_language=self.target_language,
                is_native_language=state["is_native_language"],
            )
            return {"out_translation": translated_text}

        def text_fix_node(state: AgentState) -> Dict[str, Any]:
            fixed_text = fix_text(
                text=state["messages"][0].content
            )
            return {"out_fixed": fixed_text}

        def text_summarization_node(state: AgentState) -> Dict[str, Any]:
            if len(state["messages"][0].content.split()) <= 100:
                return None

            return {"out_tldr": text_summarization(
                text=state["messages"][0].content,
                native_language=self.native_language)}

        def tz_conversion_node(state: AgentState) -> Dict[str, Any]:
            system_msg = SystemMessage(
                time_zone_prompt.format(current_location=self.current_location, query_language=state["query_language"]))
            return self.invoke_llm_with_tools(
                tools=[convert_time],
                system_message=system_msg,
                user_message=state["messages"][0]
            )

        def tz_conversion_outro_node(state: AgentState) -> Dict[str, Any]:
            tz_conversion_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)
            response = tz_conversion_llm.invoke(state["messages"])
            return {"out_tz_conversion": response.content}

        def math_formula_calculation_node(state: AgentState) -> Dict[str, Any]:
            math_formula_calculation_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)
            response = math_formula_calculation_llm.invoke([SystemMessage(math_formula_calculation_prompt), state["messages"][0]])
            calculation_result = calculate_formula(response.content)
            return {
                "out_math_result": str(calculation_result),
                "out_math_script": response.content
            }

        def currency_conversion_node(state: AgentState) -> Dict[str, Any]:
            system_msg = SystemMessage(
                currency_conversion_prompt.format(native_currency=self.native_currency))
            return self.invoke_llm_with_tools(
                tools=[convert_currency],
                system_message=system_msg,
                user_message=state["messages"][0]
            )

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

        def bash_command_node(state: AgentState) -> Dict[str, Any]:
            bash_command = generate_bash_command(state["messages"][0].content)
            return {"out_bash_command": bash_command}

        builder = StateGraph(AgentState)

        builder.add_node(task_router_node)
        builder.add_node(text_task_node)
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
        builder.add_conditional_edges(
            "task_router_node",
            lambda x: x["tasks"],
            {
                "text_task": "text_task_node",
                "tz_conversion": "tz_conversion_node",
                "math_formula_calculation": "math_formula_calculation_node",
                "convert_currency": "currency_conversion_node",
                "bash_command": "bash_command_node"
            }
        )

        builder.add_edge("text_task_node", "text_translation_node")
        builder.add_edge("text_task_node", "text_fix_node")
        builder.add_edge("text_task_node", "text_summarization_node")

        builder.add_edge("text_translation_node", END)
        builder.add_edge("text_fix_node", END)
        builder.add_edge("text_summarization_node", END)

        builder.add_edge("tz_conversion_node", "tz_conversion_tool_node")
        builder.add_edge("tz_conversion_tool_node", "tz_conversion_outro_node")

        builder.add_edge("math_formula_calculation_node", END)

        builder.add_edge("currency_conversion_node", "currency_conversion_tool_node")
        builder.add_edge("currency_conversion_tool_node", "currency_conversion_outro_node")
        builder.add_edge("currency_conversion_outro_node", END)

        builder.add_edge("bash_command_node", END)

        builder.add_edge("tz_conversion_outro_node", END)

        return builder.compile()


if __name__ == "__main__":
    agent = AgentBuilder(native_currency="EUR").build()
