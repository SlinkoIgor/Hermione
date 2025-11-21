from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.tools.function_calculator import calculate_formula
from src.tools.llm_tools import translate_text, fix_text, text_summarization, text_reformulation
from src.llm_providers import get_openai_llm, get_litellm_llm
from textwrap import dedent
from typing import Dict, Any, List, Literal, Union
from dataclasses import dataclass, field
import logging
import asyncio

logger = logging.getLogger(__name__)


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

router_prompt = dedent("""
    Analyze the user input and determine which tasks it belongs to. Multiple tasks can be relevant for a single input.

    Possible tasks:
    1. math_formula_calculation - If the input has a math formula
    2. text_task - all other cases

    In cases when you doubt whether to include a task in the list – it's better to include it.

    Language detection:
    - Identify the primary language of the user input (e.g., Russian, English, Spanish, etc.)
    - The native language is: {native_language}
    - Determine if the user input is written in {native_language} by examining the actual text content, script, and vocabulary
    - If the input contains text primarily in {native_language}, set is_native_language to "True"
    - If the input is in any other language, set is_native_language to "False"
    - Be precise: if the user writes in {native_language}, you MUST return "True" for is_native_language

    Return ONLY the task names, query_language, and is_native_language as a string with comma delimiters, nothing else.

    Return format: "task1,task2,...,taskN,query_language,is_native_language"
    Examples:
    - Input in {native_language}: "text_task,{native_language},True"
    - Input in English: "text_task,English,False"
    - Input in Spanish: "text_task,Spanish,False"

    The second-to-last part (query_language) should be the detected language name.
    The last part (is_native_language) must be "True" if the input is in {native_language}, "False" otherwise.
    """)


@dataclass
class AgentState:
    messages: List[Any] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)
    is_native_language: bool = False
    query_language: str = ""
    tool_warning: bool = False
    existent: str = ""
    out_math_result: str = ""
    out_math_script: str = ""
    out_translation: str = ""
    out_fixed: str = ""
    out_tldr: str = ""
    out_reformulation: str = ""

    def update(self, updates: Dict[str, Any]):
        for key, value in updates.items():
            if key == "tool_warning":
                setattr(self, key, getattr(self, key) or value)
            elif key == "messages":
                if isinstance(value, list):
                    self.messages.extend(value)
                else:
                    self.messages.append(value)
            else:
                setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages": self.messages,
            "tasks": self.tasks,
            "is_native_language": self.is_native_language,
            "query_language": self.query_language,
            "tool_warning": self.tool_warning,
            "existent": self.existent,
            "out_math_result": self.out_math_result,
            "out_math_script": self.out_math_script,
            "out_translation": self.out_translation,
            "out_fixed": self.out_fixed,
            "out_tldr": self.out_tldr,
            "out_reformulation": self.out_reformulation,
        }


class Agent:
    def __init__(self, builder: 'AgentBuilder'):
        self.builder = builder

    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        import asyncio
        return asyncio.run(self.ainvoke(input_data))

    async def ainvoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        state = AgentState()
        if "messages" in input_data:
            state.messages = input_data["messages"]

        await self.builder._run_agent(state)

        return state.to_dict()

    async def ainvoke_streaming(self, input_data: Dict[str, Any]):
        state = AgentState()
        if "messages" in input_data:
            state.messages = input_data["messages"]

        async for result in self.builder._run_agent_streaming(state):
            yield result


class AgentBuilder:
    def __init__(
        self,
        native_language: str = "Русский",
        target_language: str = "English",
        native_currency: str = "EUR",
        current_location: str = "Asia/Nicosia",
        base_model: Union[str, List[str]] = "gpt-5",
        fast_model: Union[str, List[str]] = "gpt-5-mini",
        temperature: float = 1,
        provider: Literal["openai", "litellm"] = "openai",
        thinking_budget: int = None,
    ):
        self.native_language = native_language
        self.target_language = target_language
        self.native_currency = native_currency
        self.current_location = current_location
        self.base_model = base_model if isinstance(base_model, list) else [base_model]
        self.fast_model = fast_model if isinstance(fast_model, list) else [fast_model]
        self.temperature = temperature
        self.provider = provider
        self.thinking_budget = thinking_budget

    def _get_llm(self, use_fast: bool = False) -> Union[ChatOpenAI, List[ChatOpenAI]]:
        model_names = self.fast_model if use_fast else self.base_model

        if len(model_names) == 1:
            if self.provider == "litellm":
                return get_litellm_llm(model_names[0], self.temperature, self.thinking_budget)
            else:
                return get_openai_llm(model_names[0], self.temperature, self.thinking_budget)

        llms = []
        for model_name in model_names:
            if self.provider == "litellm":
                llms.append(get_litellm_llm(model_name, self.temperature, self.thinking_budget))
            else:
                llms.append(get_openai_llm(model_name, self.temperature, self.thinking_budget))
        return llms

    def _get_single_llm(self, use_fast: bool = False) -> ChatOpenAI:
        model_names = self.fast_model if use_fast else self.base_model
        model_name = model_names[0]

        if self.provider == "litellm":
            return get_litellm_llm(model_name, self.temperature, self.thinking_budget)
        else:
            return get_openai_llm(model_name, self.temperature, self.thinking_budget)

    def _get_model_info(self, use_fast: bool = False) -> str:
        model_names = self.fast_model if use_fast else self.base_model
        reasoning_effort = "low" if self.thinking_budget is not None else "None"
        return f"provider={self.provider}, models={model_names}, reasoning_effort={reasoning_effort}"

    async def _task_router_node(self, state: AgentState) -> Dict[str, Any]:
        router_llm = self._get_single_llm(use_fast=True)
        logger.info(f"[MODEL_INFO] task_router_node: {self._get_model_info(use_fast=True)}")
        task_message = SystemMessage(router_prompt.format(native_language=self.native_language))
        user_message = state.messages[0]
        user_content = user_message.content[:200] if hasattr(user_message, "content") and user_message.content else ""
        task_response = await router_llm.ainvoke([task_message, HumanMessage(content=user_content)])
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
                "existent": user_message.content}

    def _get_routes(self, state: AgentState) -> list[str]:
        routes = []
        for task in state.tasks:
            if task == "text_task":
                if len(state.messages[0].content.split()) > 100:
                    routes.append("text_summarization_node")
                routes.append("text_translation_node")
                routes.append("text_fix_node")
                routes.append("text_reformulation_node")
            elif task == "math_formula_calculation":
                routes.append(f"{task}_node")
        return routes

    async def _text_translation_node(self, state: AgentState, llm: ChatOpenAI, model_name: str = None) -> Dict[str, Any]:
        model_info = f"provider={self.provider}, model={model_name or 'unknown'}"
        logger.info(f"[MODEL_INFO] text_translation_node: {model_info}")
        translated_text = await translate_text(
            text=state.messages[0].content,
            native_language=self.native_language,
            target_language=self.target_language,
            is_native_language=state.is_native_language,
            llm=llm
        )
        return {"out_translation": translated_text}

    async def _text_fix_node(self, state: AgentState, llm: ChatOpenAI, model_name: str = None) -> Dict[str, Any]:
        model_info = f"provider={self.provider}, model={model_name or 'unknown'}"
        logger.info(f"[MODEL_INFO] text_fix_node: {model_info}")
        fixed_text = await fix_text(
            text=state.messages[0].content,
            llm=llm
        )
        return {"out_fixed": fixed_text}

    async def _text_summarization_node(self, state: AgentState, llm: ChatOpenAI, model_name: str = None) -> Dict[str, Any]:
        model_info = f"provider={self.provider}, model={model_name or 'unknown'}"
        logger.info(f"[MODEL_INFO] text_summarization_node: {model_info}")
        tldr_text = await text_summarization(
            text=state.messages[0].content,
            native_language=self.native_language,
            llm=llm
        )
        return {"out_tldr": tldr_text}

    async def _text_reformulation_node(self, state: AgentState, llm: ChatOpenAI, model_name: str = None) -> Dict[str, Any]:
        model_info = f"provider={self.provider}, model={model_name or 'unknown'}"
        logger.info(f"[MODEL_INFO] text_reformulation_node: {model_info}")
        reformulated_text = await text_reformulation(
            text=state.messages[0].content,
            llm=llm
        )
        return {"out_reformulation": reformulated_text}

    async def _math_formula_calculation_node(self, state: AgentState) -> Dict[str, Any]:
        math_formula_calculation_llm = self._get_single_llm(use_fast=True)
        logger.info(f"[MODEL_INFO] math_formula_calculation_node: {self._get_model_info(use_fast=True)}")
        response = await math_formula_calculation_llm.ainvoke([SystemMessage(math_formula_calculation_prompt), state.messages[0]])
        calculation_result = calculate_formula(response.content)
        return {
            "out_math_result": str(calculation_result),
            "out_math_script": response.content
        }

    def _get_tag_for_model(self, model_name: str, num_models: int = 1) -> str:
        if num_models <= 1:
            return ""
        if "gemini" in model_name.lower():
            return "[g]"
        elif "gpt" in model_name.lower():
            return "[o]"
        return ""

    async def _run_agent_streaming(self, state: AgentState):
        result = await self._task_router_node(state)
        state.update(result)
        
        # Yield existent text first if available
        if state.existent:
            yield {
                "output_key": "existent",
                "value": state.existent,
                "tag": "",
                "model": "router"
            }

        routes = self._get_routes(state)
        llms = self._get_llm(use_fast=False)
        model_names = self.base_model

        if not isinstance(llms, list):
            llms = [llms]
            model_names = [model_names[0]] if isinstance(model_names, list) else [model_names]

        num_models = len(llms)
        tasks_list = []
        metadata_list = []

        for route in routes:
            for i, llm in enumerate(llms):
                model_name = model_names[i] if i < len(model_names) else "unknown"
                task = None
                
                if route == "text_translation_node":
                    task = asyncio.create_task(self._text_translation_node(state, llm, model_name))
                    metadata = {"route": route, "model": model_name, "output_key": "out_translation"}
                elif route == "text_fix_node":
                    task = asyncio.create_task(self._text_fix_node(state, llm, model_name))
                    metadata = {"route": route, "model": model_name, "output_key": "out_fixed"}
                elif route == "text_summarization_node":
                    task = asyncio.create_task(self._text_summarization_node(state, llm, model_name))
                    metadata = {"route": route, "model": model_name, "output_key": "out_tldr"}
                elif route == "text_reformulation_node":
                    task = asyncio.create_task(self._text_reformulation_node(state, llm, model_name))
                    metadata = {"route": route, "model": model_name, "output_key": "out_reformulation"}
                elif route == "math_formula_calculation_node":
                    task = asyncio.create_task(self._math_formula_calculation_node(state))
                    metadata = {"route": route, "model": model_name, "output_key": "out_math_result"}
                
                if task:
                    tasks_list.append(task)
                    metadata_list.append(metadata)

        if tasks_list:
            pending = set(tasks_list)
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                
                for completed_task in done:
                    try:
                        result = await completed_task
                        task_index = tasks_list.index(completed_task)
                        metadata = metadata_list[task_index]
                        
                        output_key = metadata["output_key"]
                        model_name = metadata["model"]
                        tag = self._get_tag_for_model(model_name, num_models)
                        
                        for key, value in result.items():
                            if key.startswith("out_"):
                                yield {
                                    "output_key": key[4:],
                                    "value": value,
                                    "tag": tag,
                                    "model": model_name
                                }
                    except Exception as e:
                        logger.error(f"Task failed: {e}", exc_info=True)
                        continue

    async def _run_agent(self, state: AgentState):
        result = await self._task_router_node(state)
        state.update(result)

        routes = self._get_routes(state)
        llms = self._get_llm(use_fast=False)
        model_names = self.base_model

        if not isinstance(llms, list):
            llms = [llms]
            model_names = [model_names[0]] if isinstance(model_names, list) else [model_names]

        num_models = len(llms)
        tasks = []
        task_metadata = []

        for route in routes:
            for i, llm in enumerate(llms):
                model_name = model_names[i] if i < len(model_names) else "unknown"
                
                if route == "text_translation_node":
                    tasks.append(self._text_translation_node(state, llm, model_name))
                    task_metadata.append({"route": route, "model": model_name, "output_key": "out_translation"})
                elif route == "text_fix_node":
                    tasks.append(self._text_fix_node(state, llm, model_name))
                    task_metadata.append({"route": route, "model": model_name, "output_key": "out_fixed"})
                elif route == "text_summarization_node":
                    tasks.append(self._text_summarization_node(state, llm, model_name))
                    task_metadata.append({"route": route, "model": model_name, "output_key": "out_tldr"})
                elif route == "text_reformulation_node":
                    tasks.append(self._text_reformulation_node(state, llm, model_name))
                    task_metadata.append({"route": route, "model": model_name, "output_key": "out_reformulation"})
                elif route == "math_formula_calculation_node":
                    tasks.append(self._math_formula_calculation_node(state))
                    task_metadata.append({"route": route, "model": model_name, "output_key": "out_math_result"})

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            aggregated = {}
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Task failed: {result}")
                    continue
                
                metadata = task_metadata[i]
                output_key = metadata["output_key"]
                model_name = metadata["model"]
                tag = self._get_tag_for_model(model_name, num_models)
                
                if output_key not in aggregated:
                    aggregated[output_key] = []
                
                for key, value in result.items():
                    if key.startswith("out_"):
                        aggregated[output_key].append({
                            "value": value,
                            "tag": tag,
                            "model": model_name
                        })
            
            for output_key, items in aggregated.items():
                if len(items) > 1:
                    state.update({output_key: items})
                elif len(items) == 1:
                    state.update({output_key: items[0]["value"]})

    def build(self) -> Agent:
        return Agent(self)


if __name__ == "__main__":
    agent = AgentBuilder(native_currency="EUR").build()
