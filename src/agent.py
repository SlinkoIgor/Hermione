from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode
from tools.function_calculator import calculate_formula
from tools.tz_convertor import convert_time
from tools.llm_tools import translate_text, fix_text, explain_word
from textwrap import dedent
from typing import Dict, Any
import asyncio
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


time_zone_prompt = dedent("""
    #Below are the examples how to solve the task:
    1. **Query:** "let's meet at H1H1:M1M1 [time_zone/location] time"
    **Answer:** "let's meet at H2H2:M2M2 [current_location] time"

    2. **Query:** "давай встретимся в 3 дня Берлину"
    **Answer:** "давай встретимся в 2 дня по Никосии"  (in this toy example the current location is set to Nicosia)

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
    4. construct the answer from the result of the convert_time function in the {language_of_query} and with correct wording
       (considering cases, declensions, etc.), deviating minimally from the original form of the sentence.
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

#     1. word_explanation - If the input is a word or two words (in any language)
router_prompt = dedent("""
    Analyze the user input and determine which task it belongs to:

    Possible tasks:
    1. tz_conversion - If the input has information about time that doesn't match the current time zone
    2. math_formula_calculation - If the input has a math formula
    3. text_task - all other cases

    Return format: task_name, language_of_query

    Return ONLY the task name and language of a query as a string with a comma delimiter, nothing else.
    """)


class AgentState(MessagesState):
    task: str
    language_of_query: str
    translated_text: str
    fixed_text: str


class AgentBuilder:
    def __init__(
        self,
        native_language: str = "Русский",
        target_language: str = "English",
        current_location: str = "Larnaca",
        model_name: str = "gpt-4o-mini",
        temperature: float = 0,
    ):
        self.native_language = native_language
        self.target_language = target_language
        self.current_location = current_location
        self.model_name = model_name
        self.temperature = temperature

    def build(self) -> Any:

        def task_router_node(state: AgentState) -> Dict[str, Any]:
            router_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)
            task_message = SystemMessage(router_prompt.format(native_language=self.native_language))
            user_message = state["messages"][0]
            user_content = user_message.content[:200] if hasattr(user_message, "content") and user_message.content else ""
            task_response = router_llm.invoke([task_message, HumanMessage(content=user_content)])
            task_name, language_of_query = task_response.content.lower().split(",")
            task_name = task_name.strip()
            language_of_query = language_of_query.strip()

            return {"task": task_name, "language_of_query": language_of_query}

        # def word_explanation_node(state: AgentState) -> Dict[str, Any]:
        #     explanation = explain_word(word=state["messages"][0].content,
        #                                native_language=self.native_language)
        #     return {"messages": AIMessage(explanation)}

        def text_task_junction_node(state: AgentState) -> Dict[str, Any]:
            return {"next": ["text_translation_node", "text_fix_node"]}

        def text_translation_node(state: AgentState) -> Dict[str, Any]:
            translated_text = translate_text(
                text=state["messages"][0].content,
                native_language=self.native_language,
                target_language=self.target_language,
                language_of_query=state["language_of_query"]
            )
            return {"translated_text": translated_text}

        def text_fix_node(state: AgentState) -> Dict[str, Any]:
            fixed_text = fix_text(
                text=state["messages"][0].content
            )
            return {"fixed_text": fixed_text}

        def text_aggregation_node(state: AgentState) -> Dict[str, Any]:
            translated_text = state.get("translated_text", "")
            fixed_text = state.get("fixed_text", "")
            output_text = f"{translated_text}\n\n=======<fixed_text>=======\n\n{fixed_text}"
            return {"messages": AIMessage(output_text)}

        def tz_conversion_node(state: AgentState) -> Dict[str, Any]:
            tz_conversion_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature).bind_tools(
                [convert_time], parallel_tool_calls=False)
            system_msg = SystemMessage(
                time_zone_prompt.format(current_location=self.current_location,
                                        language_of_query=state["language_of_query"]))
            response = tz_conversion_llm.invoke([system_msg, state["messages"][0]])
            return {"messages": [system_msg, response]}

        def tz_conversion_outro_node(state: AgentState) -> Dict[str, Any]:
            tz_conversion_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)
            response = tz_conversion_llm.invoke(state["messages"])
            return {"messages": response}

        def math_formula_calculation_node(state: AgentState) -> Dict[str, Any]:
            math_formula_calculation_llm = ChatOpenAI(model=self.model_name, temperature=self.temperature).bind_tools(
                [calculate_formula], parallel_tool_calls=False)
            system_msg = SystemMessage(math_formula_calculation_prompt)
            response = math_formula_calculation_llm.invoke([system_msg, state["messages"][0]])
            return {"messages": [system_msg, response]}

        builder = StateGraph(AgentState)

        builder.add_node(task_router_node)
        builder.add_node(text_task_junction_node)
        builder.add_node(text_translation_node)
        builder.add_node(text_fix_node)
        builder.add_node(text_aggregation_node)
        builder.add_node(tz_conversion_node)
        builder.add_node(math_formula_calculation_node)

        builder.add_node(ToolNode(tools=[convert_time], name="tz_conversion_tool_node"))
        builder.add_node(tz_conversion_outro_node)
        builder.add_node(ToolNode(tools=[calculate_formula], name="math_formula_calculation_tool_node"))

        builder.add_edge(START, "task_router_node")
        builder.add_conditional_edges(
            "task_router_node",
            lambda x: x["task"],
            {
                "text_task": "text_task_junction_node",
                "tz_conversion": "tz_conversion_node",
                "math_formula_calculation": "math_formula_calculation_node"
            }
        )

        builder.add_edge("text_task_junction_node", "text_translation_node")
        builder.add_edge("text_task_junction_node", "text_fix_node")

        builder.add_edge("text_translation_node", "text_aggregation_node")
        builder.add_edge("text_fix_node", "text_aggregation_node")
        builder.add_edge("text_aggregation_node", END)

        builder.add_edge("tz_conversion_node", "tz_conversion_tool_node")
        builder.add_edge("tz_conversion_tool_node", "tz_conversion_outro_node")

        builder.add_edge("math_formula_calculation_node", "math_formula_calculation_tool_node")

        # builder.add_edge("word_explanation_node", END)
        builder.add_edge("tz_conversion_outro_node", END)
        builder.add_edge("math_formula_calculation_tool_node", END)

        return builder.compile()


def test_agent(agent):
    all_tests_passed = True

    # Test case 1: Math formula calculation
    try:
        messages1 = agent.invoke(
            {"messages": [HumanMessage("log10(1000 * 66)")]})
        result1 = str(messages1['messages'][-1].content)
        expected1 = "4.81954393554"
        if not result1.startswith(expected1):
            print(f"❌ Math formula calculation failed, got: {result1}, expected: {expected1}")
            all_tests_passed = False
        else:
            print(f"✅ Math formula calculation passed: {result1}")
    except Exception as e:
        print(f"❌ Math formula calculation failed with error: {str(e)}")
        all_tests_passed = False

    # # Test case 2: Word explanation
    messages2 = agent.invoke(
        {"messages": [HumanMessage("Photosynthesis")]})
    print(messages2['messages'])
    result2 = str(messages2['messages'][-1].content)
    if not "Фотосинтез (" in result2:
        print(f"❌ Word explanation failed, got: {result2}")
        all_tests_passed = False
    else:
        print(f"✅ Word explanation passed")

    # # Test case 3: Time zone conversion (Russian)
    try:
        messages3 = agent.invoke(
            {"messages": [HumanMessage("давай встретимся в 3 дня по Барселоне")]})
        result3 = str(messages3['messages'][-1].content)
        expected3 = "давай встретимся в 4 дня по Никосии"
        if result3 != expected3:
            print(f"❌ Time zone conversion (Russian) failed, got: {result3}, expected: {expected3}")
            all_tests_passed = False
        else:
            print(f"✅ Time zone conversion (Russian) passed: {result3}")
    except Exception as e:
        print(f"❌ Time zone conversion (Russian) failed with error: {str(e)}")
        all_tests_passed = False

    # # Test case 4: Text translation
    try:
        messages4 = agent.invoke(
            {"messages": [HumanMessage("The issue is that LangChain's bind_tools expects a function with a valid __name__ attribute, which classes (even callables) don't naturally have. Since functools.partial and lambda also don't provide __name__, the best approach is to use a decorator-based wrapper to dynamically set __name__.")]})
        result4 = str(messages4['messages'][-1].content)
        print(result4)
        expected4 = "Проблема заключается в том, что"
        if not expected4 in result4:
            print(f"❌ Text translation failed, got: {result4}")
            print(f"Expected: {expected4}")
            all_tests_passed = False
        else:
            print(f"✅ Text translation passed")
    except Exception as e:
        print(f"❌ Text translation failed with error: {str(e)}")
        all_tests_passed = False

    # Test case 5: Time zone conversion (English)
    try:
        messages5 = agent.invoke(
            {"messages": [HumanMessage("can you make it after 4 PM Berlin time?")]})
        result5 = str(messages5['messages'][-1].content)
        expected5 = "can you make it after 5 PM Larnaca time?"
        if result5 != expected5:
            print(f"❌ Time zone conversion (English) failed, got: {result5}, expected: {expected5}")
            all_tests_passed = False
        else:
            print(f"✅ Time zone conversion (English) passed: {result5}")
    except Exception as e:
        print(f"❌ Time zone conversion (English) failed with error: {str(e)}")
        all_tests_passed = False

    if all_tests_passed:
        print("✅ All test cases passed successfully!")
    else:
        print("❌ Some test cases failed. See above for details.")

    return all_tests_passed

if __name__ == "__main__":
    agent = AgentBuilder().build()
    # test_agent(AgentBuilder().build())
