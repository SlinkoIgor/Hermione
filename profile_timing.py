import time
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from langchain_core.messages import HumanMessage
from agent import AgentBuilder, get_timing_data, clear_timing_data
from agent_config import get_agent_config

async def run_agent_async(provider: str, human_message: HumanMessage):
    clear_timing_data()
    start_time = time.time()

    agent_start = time.time()
    config = get_agent_config(provider=provider)
    agent_instance = AgentBuilder(provider=provider, **config).build()
    agent_build_time = time.time() - agent_start

    invoke_start = time.time()
    result = await agent_instance.ainvoke({"messages": [human_message]})
    invoke_time = time.time() - invoke_start

    total_time = time.time() - start_time
    node_timings = get_timing_data()

    output = {}
    for key, value in result.items():
        if key.startswith("out_") and value:
            output_key = key[4:]
            if output_key == "text":
                continue
            if provider == "litellm":
                output_key = f"🚄{output_key}"
            output[output_key] = value

    return {
        "provider": provider,
        "agent_build_time": agent_build_time,
        "invoke_time": invoke_time,
        "total_time": total_time,
        "node_timings": node_timings,
        "output": output
    }

def print_node_timings(node_timings, provider_name):
    if not node_timings:
        print("  No node timing data available")
        return

    print(f"\n  Node execution breakdown:")
    total_node_time = sum(t['time'] for t in node_timings)
    for timing in sorted(node_timings, key=lambda x: x['time'], reverse=True):
        percentage = (timing['time'] / total_node_time * 100) if total_node_time > 0 else 0
        print(f"    {timing['node']:30s} {timing['time']:6.3f}s ({percentage:5.1f}%)")

async def profile_simple_request():
    test_message = "Hello, how are you?"
    human_message = HumanMessage(content=test_message)

    print(f"Testing with message: '{test_message}'")
    print("=" * 80)

    print("\n[1] Testing OpenAI agent:")
    print("-" * 80)
    openai_result = await run_agent_async("openai", human_message)
    print(f"  Agent build time: {openai_result['agent_build_time']:.3f}s")
    print(f"  Invoke time:      {openai_result['invoke_time']:.3f}s")
    print(f"  Total time:       {openai_result['total_time']:.3f}s")
    print(f"  Output keys:      {list(openai_result['output'].keys())}")
    print_node_timings(openai_result['node_timings'], "OpenAI")

    print("\n[2] Testing LiteLLM agent:")
    print("-" * 80)
    litellm_result = await run_agent_async("litellm", human_message)
    print(f"  Agent build time: {litellm_result['agent_build_time']:.3f}s")
    print(f"  Invoke time:      {litellm_result['invoke_time']:.3f}s")
    print(f"  Total time:       {litellm_result['total_time']:.3f}s")
    print(f"  Output keys:      {list(litellm_result['output'].keys())}")
    print_node_timings(litellm_result['node_timings'], "LiteLLM")

    print("\n[3] Testing parallel execution:")
    print("-" * 80)
    parallel_start = time.time()
    results = await asyncio.gather(
        run_agent_async("openai", human_message),
        run_agent_async("litellm", human_message)
    )
    parallel_time = time.time() - parallel_start

    print(f"  Parallel total time: {parallel_time:.3f}s")
    print(f"  OpenAI time:         {results[0]['total_time']:.3f}s")
    print(f"  LiteLLM time:        {results[1]['total_time']:.3f}s")
    print(f"  Time saved:          {results[0]['total_time'] + results[1]['total_time'] - parallel_time:.3f}s")

    print("\n" + "=" * 80)
    print("SUMMARY - Slowest Operations:")
    print("-" * 80)

    openai_nodes = {t['node']: t['time'] for t in results[0]['node_timings']}
    litellm_nodes = {t['node']: t['time'] for t in results[1]['node_timings']}

    all_nodes = set(openai_nodes.keys()) | set(litellm_nodes.keys())

    print(f"\n  {'Node':<30s} {'OpenAI':<12s} {'LiteLLM':<12s} {'Difference':<12s}")
    print("  " + "-" * 66)

    for node in sorted(all_nodes, key=lambda n: max(openai_nodes.get(n, 0), litellm_nodes.get(n, 0)), reverse=True):
        openai_time = openai_nodes.get(node, 0)
        litellm_time = litellm_nodes.get(node, 0)
        diff = openai_time - litellm_time
        print(f"  {node:<30s} {openai_time:>8.3f}s   {litellm_time:>8.3f}s   {diff:>+8.3f}s")

    print(f"\n  Overall invoke times:")
    print(f"    OpenAI:  {results[0]['invoke_time']:.3f}s")
    print(f"    LiteLLM: {results[1]['invoke_time']:.3f}s")
    print(f"    Difference: {results[0]['invoke_time'] - results[1]['invoke_time']:+.3f}s")

    slowest_openai = max(results[0]['node_timings'], key=lambda x: x['time']) if results[0]['node_timings'] else None
    slowest_litellm = max(results[1]['node_timings'], key=lambda x: x['time']) if results[1]['node_timings'] else None

    if slowest_openai:
        print(f"\n  Slowest OpenAI node:  {slowest_openai['node']} ({slowest_openai['time']:.3f}s)")
    if slowest_litellm:
        print(f"  Slowest LiteLLM node: {slowest_litellm['node']} ({slowest_litellm['time']:.3f}s)")

if __name__ == "__main__":
    asyncio.run(profile_simple_request())

