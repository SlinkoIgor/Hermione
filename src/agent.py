from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode
from src.tools.function_calculator import calculate_formula, format_output
from src.tools.tz_convertor import convert_time
from src.tools.llm_tools import translate_text, fix_text, text_summarization
from src.tools.currency_converter import convert_currency
from textwrap import dedent
from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


time_zone_prompt = dedent("""
    #Below are the examples how to solve the task:
    1. **Query:** "let's meet at H1H1:M1M1 [time_zone/location] time"
    **Answer:** "let's meet at H2H2:M2M2 [current_location] time"

    2. **Query:** "давай встретимся в полночь по Берлину"
    **Answer:** "давай встретимся в час ночи по Никосии"  (in this toy example the current location is set to Nicosia)

    3. **Query:** "можем ли мы перенести встречу в 10 AM по NY на час вперед?"
    **Answer:** "можем ли мы перенести встречу в 3 PM по Барселоне на час вперед?" (in this toy example the current location is set to Barcelona)

    In these conversations:
    - H1H1:M1M1 is time of some [time_zone] (e.g. CET, UTC+2) or [location] (e.g. Berlin)
    - H2H2:M2M2 is time of [current_location]
    - [current_location] is {current_location}

    **RETURN ONLY THE ANSWER, NO OTHER TEXT.**

    To generate the answer, you need to:
    1. convert [time_zone/location] to the correct_time_zone in python format (e.g. "Europe/Berlin", "America/New_York")
    2. convert current_location which is {current_location} to the correct_current_time_zone in python format (e.g. "Europe/Berlin", "America/New_York")
    3. run a function convert_time with the correct arguments (H1H1:M1M1, correct_time_zone, correct_current_time_zone)
    4. construct the answer from the result of the convert_time function with the same wording as the original sentence.
        Do not add new text, only rewrite the text with the new time.

    YOU MUST CALL THE TOOL!!!
    YOU MUST CALL THE TOOL!!!
    """)

math_formula_calculation_prompt = dedent("""
    #Below are the examples how to solve the task:

    **Query:** "- (1/N) * SUM ( y_true * log(y_pred) ) where N=5 and y_true=[0,0,0,0,0] and y_pred=[0.1,0.2,0.3,0.4,0.5]"
    **Answer:** "0."

    **RETURN ONLY THE ANSWER, NO OTHER TEXT.**

    To generate the answer, you need to:
    1. Write a python code that calculates the formula.
       You are allowed to use the following safe built-ins: abs, min, max, sum, len, range, math, numpy, datetime
       For the previous example, the code should be:
       ```python
       import numpy as np

       N = 5
       y_true = [0, 0, 0, 0, 0]
       y_pred = [0.1, 0.2, 0.3, 0.4, 0.5]

       result = -(1/N) * sum(y_true[i] * np.log(y_pred[i]) for i in range(len(y_true)))
       ```
    2. trigger calculate_formula tool with the code written by you as an argument
    3. Pick the result from the calculate_formula tool call

    YOU MUST CALL THE TOOL!!!
    YOU MUST CALL THE TOOL!!!
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
    Analyze the user input and determine which task it belongs to:

    Possible tasks:
    1. tz_conversion - If the input has information about time that doesn't match the current time zone
    2. math_formula_calculation - If the input has a math formula
    3. convert_currency - If the input has information about currency conversion
    4. text_task - all other cases

    Return format: task_name, is_native_language

    Return ONLY the task name and whether the text is in the native language ({native_language}) as a string with a comma delimiter, nothing else.
    The second part should be "True" if the text is in {native_language} or "False" otherwise.
    """)


class AgentState(MessagesState):
    task: str
    is_native_language: bool
    translated_text: str
    fixed_text: str
    summarized_text: str


class AgentBuilder:
    def __init__(
        self,
        native_language: str = "Русский",
        target_language: str = "English",
        current_location: str = "Larnaca",
        native_currency: str = "EUR",
        model_name: str = "gpt-4o-mini",
        temperature: float = 0,
    ):
        self.native_language = native_language
        self.target_language = target_language
        self.current_location = current_location
        self.native_currency = native_currency
        self.model_name = model_name
        self.temperature = temperature

    def build(self) -> Any:

        def task_router_node(state: AgentState) -> Dict[str, Any]:
            router_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)
            task_message = SystemMessage(router_prompt.format(native_language=self.native_language))
            user_message = state["messages"][0]
            user_content = user_message.content[:200] if hasattr(user_message, "content") and user_message.content else ""
            task_response = router_llm.invoke([task_message, HumanMessage(content=user_content)])
            task_name, is_native_language = task_response.content.lower().split(",")
            task_name = task_name.strip()
            is_native_language = is_native_language.strip() == "true"

            return {"task": task_name, "is_native_language": is_native_language}

        def text_task_junction_node(state: AgentState) -> Dict[str, Any]:
            text = state["messages"][0].content
            words = [word for word in text.split() if word.strip()]
            word_count = len(words)
            should_summarize = word_count > 100
            return {"should_summarize": should_summarize}

        def text_translation_node(state: AgentState) -> Dict[str, Any]:
            translated_text = translate_text(
                text=state["messages"][0].content,
                native_language=self.native_language,
                target_language=self.target_language,
                is_native_language=state["is_native_language"]
            )
            return {"translated_text": translated_text}

        def text_fix_node(state: AgentState) -> Dict[str, Any]:
            fixed_text = fix_text(
                text=state["messages"][0].content
            )
            return {"fixed_text": fixed_text}

        def text_summarization_node(state: AgentState) -> Dict[str, Any]:
            summarized_text = text_summarization(
                text=state["messages"][0].content,
                native_language=self.native_language
            )
            return {"summarized_text": summarized_text}

        def text_aggregation_node(state: AgentState) -> Dict[str, Any]:
            translated_text = state.get("translated_text", "")
            fixed_text = state.get("fixed_text", "")
            summarized_text = state.get("summarized_text", "")

            output_parts = []

            if summarized_text:
                output_parts.append(f"=======<tl;dr>=======\n\n{summarized_text}")

            output_parts.append(f"=======<translation>=======\n\n{translated_text}")
            output_parts.append(f"=======<fixed_text>=======\n\n{fixed_text}")

            output_text = "\n\n".join(output_parts)

            return {"messages": AIMessage(output_text)}

        def tz_conversion_node(state: AgentState) -> Dict[str, Any]:
            tz_conversion_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature).bind_tools(
                [convert_time], parallel_tool_calls=False)
            system_msg = SystemMessage(
                time_zone_prompt.format(current_location=self.current_location))
            response = tz_conversion_llm.invoke([system_msg, state["messages"][0]])
            return {"messages": [system_msg, response]}

        def tz_conversion_outro_node(state: AgentState) -> Dict[str, Any]:
            tz_conversion_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)
            response = tz_conversion_llm.invoke(state["messages"])
            return {"messages": AIMessage(f'=======<tz_conversion>=======\n\n{response.content}')}

        def math_formula_calculation_node(state: AgentState) -> Dict[str, Any]:
            math_formula_calculation_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature).bind_tools(
                [calculate_formula], parallel_tool_calls=False)
            system_msg = SystemMessage(math_formula_calculation_prompt)
            response = math_formula_calculation_llm.invoke([system_msg, state["messages"][0]])
            original_input = state["messages"][0].content
            code_with_result = f"result = {original_input}"
            calculation_result = calculate_formula(code_with_result)
            formatted_result = format_output(original_input, calculation_result)
            return {"messages": AIMessage(formatted_result)}

        def currency_conversion_node(state: AgentState) -> Dict[str, Any]:
            currency_conversion_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature).bind_tools(
                [convert_currency], parallel_tool_calls=False)
            system_msg = SystemMessage(
                currency_conversion_prompt.format(native_currency=self.native_currency))
            response = currency_conversion_llm.invoke([system_msg, state["messages"][0]])
            return {"messages": [system_msg, response]}

        def currency_conversion_outro_node(state: AgentState) -> Dict[str, Any]:
            # Get the last message which should contain the tool response
            last_message = state["messages"][-1]

            # Extract the result from the tool response
            if hasattr(last_message, 'content'):
                try:
                    # Parse the string representation of the result
                    import ast
                    result_dict = ast.literal_eval(last_message.content)

                    result = result_dict.get('result')
                    amount = result_dict.get('amount', 0)
                    source_currency = result_dict.get('source_currency', '')
                    target_currency = result_dict.get('target_currency', '')

                    # Check if we have a valid result
                    if result is not None:
                        # Format the response
                        formatted_response = f"{amount} {source_currency} == {result:.2f} {target_currency}"
                    else:
                        error_msg = result_dict.get('error', 'Unknown error')
                        formatted_response = f"Error: {error_msg}"
                except (ValueError, SyntaxError):
                    formatted_response = "Error: Could not parse currency conversion result"
            else:
                formatted_response = "Error: Could not extract currency conversion result"

            return {"messages": AIMessage(f'=======<convert_currency>=======\n\n{formatted_response}')}

        builder = StateGraph(AgentState)

        builder.add_node(task_router_node)
        builder.add_node(text_task_junction_node)
        builder.add_node(text_translation_node)
        builder.add_node(text_fix_node)
        builder.add_node(text_summarization_node)
        builder.add_node(text_aggregation_node)
        builder.add_node(tz_conversion_node)
        builder.add_node(math_formula_calculation_node)
        builder.add_node(currency_conversion_node)
        builder.add_node(currency_conversion_outro_node)

        builder.add_node(ToolNode(tools=[convert_time], name="tz_conversion_tool_node"))
        builder.add_node(tz_conversion_outro_node)
        builder.add_node(ToolNode(tools=[calculate_formula], name="math_formula_calculation_tool_node"))
        builder.add_node(ToolNode(tools=[convert_currency], name="currency_conversion_tool_node"))

        builder.add_edge(START, "task_router_node")
        builder.add_conditional_edges(
            "task_router_node",
            lambda x: x["task"],
            {
                "text_task": "text_task_junction_node",
                "tz_conversion": "tz_conversion_node",
                "math_formula_calculation": "math_formula_calculation_node",
                "convert_currency": "currency_conversion_node"
            }
        )

        builder.add_edge("text_task_junction_node", "text_translation_node")
        builder.add_edge("text_task_junction_node", "text_fix_node")

        builder.add_conditional_edges(
            "text_task_junction_node",
            lambda x: "text_summarization_node" if x.get("should_summarize", False) else "skip_summarization",
            {
                "text_summarization_node": "text_summarization_node",
                "skip_summarization": "text_aggregation_node"
            }
        )

        builder.add_edge("text_translation_node", "text_aggregation_node")
        builder.add_edge("text_fix_node", "text_aggregation_node")
        builder.add_edge("text_summarization_node", "text_aggregation_node")
        builder.add_edge("text_aggregation_node", END)

        builder.add_edge("tz_conversion_node", "tz_conversion_tool_node")
        builder.add_edge("tz_conversion_tool_node", "tz_conversion_outro_node")

        builder.add_edge("math_formula_calculation_node", "math_formula_calculation_tool_node")
        builder.add_edge("math_formula_calculation_tool_node", END)

        builder.add_edge("currency_conversion_node", "currency_conversion_tool_node")
        builder.add_edge("currency_conversion_tool_node", "currency_conversion_outro_node")
        builder.add_edge("currency_conversion_outro_node", END)

        builder.add_edge("tz_conversion_outro_node", END)

        return builder.compile()


if __name__ == "__main__":
    agent = AgentBuilder(native_currency="EUR").build()
