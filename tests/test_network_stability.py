import argparse
import asyncio
import os
import sys
import time
import httpx
from dotenv import load_dotenv
from dataclasses import dataclass, field

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from src.agent import AgentBuilder
from src.agent_config import get_agent_config
from langchain_core.messages import HumanMessage


LITELLM_HOST = os.getenv("LITELLM_HOST", "https://litellm.labs.jb.gg")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

PROMPTS = [
    "log10(1000 * 66)",
    "Photosynthesis",
    "2 + 2 * 2",
]


@dataclass
class Stats:
    provider: str
    total: int = 0
    ok: int = 0
    fail: int = 0
    errors: list = field(default_factory=list)
    latencies: list = field(default_factory=list)


def percentile(data, pct):
    if not data:
        return 0
    s = sorted(data)
    idx = min(int(len(s) * pct / 100), len(s) - 1)
    return s[idx]


def print_stats(stats: Stats):
    n = len(stats.latencies)
    avg_lat = sum(stats.latencies) / n if n else 0
    min_lat = min(stats.latencies) if n else 0
    max_lat = max(stats.latencies) if n else 0
    med = percentile(stats.latencies, 50)
    p95 = percentile(stats.latencies, 95)

    rate = stats.ok / stats.total * 100 if stats.total else 0
    print(f"\n{'=' * 60}")
    print(f"  {stats.provider.upper()}")
    print(f"{'=' * 60}")
    print(f"  Total: {stats.total}  |  OK: {stats.ok}  |  FAIL: {stats.fail}  |  Success rate: {rate:.0f}%")
    print(f"  Latency  min: {min_lat:.2f}s  |  med: {med:.2f}s  |  avg: {avg_lat:.2f}s  |  p95: {p95:.2f}s  |  max: {max_lat:.2f}s")
    if stats.errors:
        print(f"  Errors:")
        for err in stats.errors:
            print(f"    [{err['round']:>2}] {err['prompt'][:40]:<40}  {err['error']}")
    print(f"{'=' * 60}")


def get_http_config(provider: str):
    if provider == "openai":
        return {
            "url": "https://api.openai.com/v1/chat/completions",
            "headers": {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            "model": "gpt-5.4-nano",
        }
    if provider == "google":
        return {
            "url": f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "headers": {"Authorization": f"Bearer {GOOGLE_API_KEY}", "Content-Type": "application/json"},
            "model": "gemini-3-flash-preview",
        }
    return {
        "url": f"{LITELLM_HOST}/chat/completions",
        "headers": {"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"},
        "model": "gemini-3-flash-preview",
    }


async def run_raw_http_test(provider: str, rounds: int, stats: Stats):
    cfg = get_http_config(provider)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(rounds):
            prompt = PROMPTS[i % len(PROMPTS)]
            payload = {
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": 50,
            }
            stats.total += 1
            t0 = time.monotonic()
            try:
                resp = await client.post(cfg["url"], headers=cfg["headers"], json=payload)
                elapsed = time.monotonic() - t0
                if 200 <= resp.status_code < 300:
                    stats.ok += 1
                    stats.latencies.append(elapsed)
                    status = "OK"
                else:
                    stats.fail += 1
                    stats.errors.append({"round": i + 1, "prompt": prompt, "error": f"HTTP {resp.status_code}"})
                    status = f"HTTP {resp.status_code}"
            except Exception as e:
                elapsed = time.monotonic() - t0
                stats.fail += 1
                stats.errors.append({"round": i + 1, "prompt": prompt, "error": f"{type(e).__name__}: {e}"})
                status = f"FAIL ({type(e).__name__})"

            print(f"  [{provider:>7}] round {i + 1:>2}/{rounds}  {elapsed:>6.2f}s  {status}")


async def run_agent_test(provider: str, rounds: int, stats: Stats):
    agent_provider = "litellm" if provider == "google" else provider
    config = get_agent_config(provider=agent_provider, thinking_budget=1000)
    if provider == "google":
        config["base_model"] = "gemini-3-flash-preview"
        config["fast_model"] = "gemini-3-flash-preview"
    agent = AgentBuilder(native_currency="EUR", provider=agent_provider, **config).build()

    for i in range(rounds):
        prompt = PROMPTS[i % len(PROMPTS)]
        stats.total += 1
        t0 = time.monotonic()
        try:
            await agent.ainvoke({"messages": [HumanMessage(prompt)]})
            elapsed = time.monotonic() - t0
            stats.ok += 1
            stats.latencies.append(elapsed)
            status = "OK"
        except Exception as e:
            elapsed = time.monotonic() - t0
            stats.fail += 1
            stats.errors.append({"round": i + 1, "prompt": prompt, "error": f"{type(e).__name__}: {e}"[:120]})
            status = f"FAIL ({type(e).__name__})"

        print(f"  [{provider:>7}] round {i + 1:>2}/{rounds}  {elapsed:>6.2f}s  {status}")


async def main():
    parser = argparse.ArgumentParser(description="Network stability test for LLM providers")
    parser.add_argument(
        "provider",
        choices=["openai", "litellm", "google", "both", "all"],
        help="which provider to test (all = openai + litellm + google)",
    )
    parser.add_argument(
        "-n", "--rounds",
        type=int,
        default=10,
        help="number of rounds per phase (default: 10)",
    )
    parser.add_argument(
        "--http-only",
        action="store_true",
        help="skip agent tests, only run raw HTTP",
    )
    parser.add_argument(
        "--agent-only",
        action="store_true",
        help="skip HTTP tests, only run agent",
    )
    args = parser.parse_args()

    provider_map = {
        "both": ["openai", "litellm"],
        "all": ["openai", "litellm", "google"],
    }
    providers = provider_map.get(args.provider, [args.provider])

    all_stats = []

    if not args.agent_only:
        print(f"\n{'=' * 60}")
        print(f"  PHASE 1: Raw HTTP requests (lightweight, no agent)")
        print(f"{'=' * 60}")
        for p in providers:
            s = Stats(provider=f"{p} (http)")
            await run_raw_http_test(p, args.rounds, s)
            all_stats.append(s)

    if not args.http_only:
        print(f"\n{'=' * 60}")
        print(f"  PHASE 2: Full agent invocations (multi-step LLM calls)")
        print(f"{'=' * 60}")
        for p in providers:
            s = Stats(provider=f"{p} (agent)")
            await run_agent_test(p, args.rounds, s)
            all_stats.append(s)

    print(f"\n\n{'#' * 60}")
    print(f"#  SUMMARY")
    print(f"{'#' * 60}")
    for s in all_stats:
        print_stats(s)


if __name__ == "__main__":
    asyncio.run(main())
