"""
End-to-end pipeline: Natural Language → XML BT → SMT Verify → ROS 2 Execute

Two independent resilience mechanisms:

  1. SMT-guided retry loop  (same provider)
       If the generated BT fails verification, the SAME provider is called
       again with the exact failure reason attached to the prompt.
       The provider does NOT change because of an SMT failure.
       Default: up to MAX_RETRIES = 3 attempts on the current provider.

       Example (all on Gemini):
         Attempt 1/3  [gemini]  → SMT FAIL (task_ordering)
         Attempt 2/3  [gemini]  → SMT FAIL (spatial_bounds)
         Attempt 3/3  [gemini]  → SMT PASS ✅

  2. Provider fallback chain  (only on API/network failure)
       Gemini → GPT-4o → Claude
       The next provider is tried ONLY if the current one raises an
       exception (missing API key, quota exceeded, network error, etc.).
       A BT that fails SMT is NOT a reason to switch providers.

       Example:
         [gemini] raises APIError → switch to [openai]
         [openai] attempts 1-3 with SMT retries → PASS ✅
"""
import argparse
import sys
import time
import logging
from typing import Optional

from llm_module.llm_client import (
    generate_behavior_tree,
    DEFAULT_PROVIDER_CHAIN,
    _build_prompt,
)
from verification.smt_verifier import SMTVerifier
from verification.config import (
    ALLOWED_ACTIONS, MAP_WIDTH, MAP_HEIGHT,
    LOOP_THRESHOLD, KNOWN_LOCATIONS, MAP_GRAPH,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Tunables ──────────────────────────────────────────────────────────────────
MAX_RETRIES    = 3                    # SMT-guided retries per provider
PROVIDER_CHAIN = DEFAULT_PROVIDER_CHAIN  # ["gemini", "openai", "anthropic"]


# ─────────────────────────────────────────────────────────────────────────────
# SMT verifier singleton — reused across all retries and providers
# ─────────────────────────────────────────────────────────────────────────────
_VERIFIER = SMTVerifier(
    allowed_actions=ALLOWED_ACTIONS,
    map_width=MAP_WIDTH,
    map_height=MAP_HEIGHT,
    loop_threshold=LOOP_THRESHOLD,
    known_locations=KNOWN_LOCATIONS,
    map_graph=MAP_GRAPH,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_smt_feedback(xml_bt: str, smt_result: dict) -> str:
    """
    Build a human-readable (and LLM-readable) rejection summary.
    Only failed properties are listed so the LLM can focus on fixing them.
    """
    lines = ["The following behavior tree was REJECTED by the safety verifier:"]
    lines.append("")
    lines.append(xml_bt.strip())
    lines.append("")
    lines.append("Violations found:")
    for chk in smt_result["checks"]:
        if not chk["passed"]:
            lines.append(f"  - [{chk['name']}] {chk['detail']}")
    lines.append("")
    lines.append(
        "You MUST fix every violation listed above. Common fixes:\n"
        "  * task_ordering      : add move_to BEFORE pick_up / place / deliver\n"
        "  * action_whitelist   : use only allowed actions\n"
        "  * reachability       : use only known locations\n"
        "  * loop_termination   : add max_iterations='N' (1 ≤ N ≤ 99) on every Repeat\n"
        "  * spatial_bounds     : keep x/y inside the map\n"
        "  * structural_validity: use only Sequence, Fallback, Repeat, Action, Condition"
    )
    return "\n".join(lines)


def _print_check_results(checks: list, smt_ms: float, passed: bool) -> None:
    status = "PASSED" if passed else "REJECTED"
    print(f"  {status} ({smt_ms:.1f} ms)")
    for chk in checks:
        icon = "✓" if chk["passed"] else "✗"
        print(f"    [{icon}] {chk['name']}: {chk['detail']}")


def _try_provider_with_retries(
    nl_input: str,
    provider: str,
    max_retries: int,
) -> dict:
    """
    Call one provider up to `max_retries` times, retrying on SMT failure.
    The provider is NOT changed here — that is the caller's responsibility.

    Returns a result dict:
        status   : "success" | "rejected" | "api_error"
        xml      : last generated XML (or None)
        checks   : last SMT check list (or [])
        errors   : last SMT error list (or [])
        attempts : how many LLM calls were made
        llm_ms   : cumulative LLM time
        smt_ms   : last SMT time
    """
    smt_feedback: Optional[str] = None
    last_result:  Optional[dict] = None
    last_xml:     Optional[str]  = None
    total_llm_ms = 0.0
    last_smt_ms  = 0.0

    for attempt in range(1, max_retries + 1):
        label    = f"Attempt {attempt}/{max_retries}"
        is_retry = attempt > 1

        # ── Stage 1: Generate BT ──────────────────────────────────────────
        print(f"\n[Stage 1] LLM Translation  ({label})  [{provider}]")
        if is_retry:
            print(f"  ↳ Same provider, retrying with SMT failure feedback ...")

        t0 = time.perf_counter()
        try:
            xml_bt = generate_behavior_tree(
                nl_input,
                provider=provider,
                smt_feedback=smt_feedback,
            )
            total_llm_ms += (time.perf_counter() - t0) * 1000
        except Exception as exc:
            total_llm_ms += (time.perf_counter() - t0) * 1000
            print(f"  ✗ [{provider}] API error: {exc}")
            # Signal the caller to try the next provider
            return {
                "status":   "api_error",
                "xml":      last_xml,
                "checks":   last_result["checks"] if last_result else [],
                "errors":   last_result["errors"]  if last_result else [],
                "attempts": attempt,
                "llm_ms":   total_llm_ms,
                "smt_ms":   last_smt_ms,
                "error_msg": str(exc),
            }

        if not xml_bt:
            print(f"  ✗ [{provider}] Returned empty response.")
            smt_feedback = (
                "The previous generation produced an empty response. "
                "Please output a valid XML behavior tree."
            )
            continue

        print(f"  ✓ [{provider}] {len(xml_bt)} chars  ({total_llm_ms:.0f} ms)")
        last_xml = xml_bt

        # ── Stage 2: SMT Verification ─────────────────────────────────────
        print(f"\n[Stage 2] SMT Verification ({label})")
        t1 = time.perf_counter()
        result      = _VERIFIER.verify(xml_bt)
        last_smt_ms = (time.perf_counter() - t1) * 1000
        last_result = result

        _print_check_results(result["checks"], last_smt_ms, result["passed"])

        if result["passed"]:
            return {
                "status":   "success",
                "xml":      xml_bt,
                "checks":   result["checks"],
                "errors":   [],
                "attempts": attempt,
                "llm_ms":   total_llm_ms,
                "smt_ms":   last_smt_ms,
            }

        # SMT failed — build feedback for the NEXT attempt on the SAME provider
        print(f"  ↳ [{provider}] SMT rejected — will retry same provider with feedback.")
        smt_feedback = _format_smt_feedback(xml_bt, result)

    # All retries exhausted on this provider (SMT kept failing, no API error)
    return {
        "status":   "rejected",
        "xml":      last_xml,
        "checks":   last_result["checks"] if last_result else [],
        "errors":   last_result["errors"]  if last_result else [],
        "attempts": max_retries,
        "llm_ms":   total_llm_ms,
        "smt_ms":   last_smt_ms,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    nl_input: str,
    execute: bool = False,
    max_retries: int = MAX_RETRIES,
    provider_chain: list = PROVIDER_CHAIN,
) -> dict:
    """
    Run the full NL2BT-Verify pipeline.

    Retry logic  : each provider gets MAX_RETRIES attempts with SMT feedback.
    Fallback logic: next provider is tried ONLY on API/network failure —
                    never because the BT failed SMT.

    Returns a result dict with keys:
        status   : "success" | "rejected" | "error"
        xml      : final XML BT
        checks   : per-property results
        attempts : total LLM calls made across all providers
        provider : provider that generated the accepted BT
        timings  : {llm_ms, smt_ms} for the final run
    """
    print(f"\n{'='*60}")
    print(f"  NL2BT-Verify Pipeline")
    print(f"  Input     : {nl_input}")
    print(f"  Providers : {' → '.join(provider_chain)}  (fallback on API failure only)")
    print(f"  Retries   : up to {max_retries} per provider  (on SMT failure)")
    print(f"{'='*60}")

    import os
    key_map = {
        "gemini":    "GEMINI_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    total_attempts = 0

    for provider in provider_chain:
        # Skip if API key is not configured
        env_key = key_map.get(provider, "")
        if env_key and not os.environ.get(env_key):
            print(f"\n  [skip] {provider} — {env_key} not set.")
            continue

        print(f"\n{'─'*60}")
        print(f"  Provider: {provider.upper()}")
        print(f"{'─'*60}")

        outcome = _try_provider_with_retries(nl_input, provider, max_retries)
        total_attempts += outcome["attempts"]

        if outcome["status"] == "success":
            print(f"\n{'='*60}")
            print(f"  ✅ SAFE — All properties verified")
            print(f"  Provider : {provider}  |  Total attempts: {total_attempts}")
            print(f"  LLM      : {outcome['llm_ms']:.0f} ms  |  SMT: {outcome['smt_ms']:.2f} ms")
            print(f"{'='*60}")

            if execute:
                print(f"\n[Stage 3] ROS 2 Execution")
                from ros2_executor.bt_executor import execute_behavior_tree
                execute_behavior_tree(outcome["xml"])

            return {
                "status":   "success",
                "xml":      outcome["xml"],
                "checks":   outcome["checks"],
                "attempts": total_attempts,
                "provider": provider,
                "timings":  {
                    "llm_ms": outcome["llm_ms"],
                    "smt_ms": outcome["smt_ms"],
                },
            }

        elif outcome["status"] == "rejected":
            # Provider worked fine (no API error) but BT kept failing SMT.
            # Do NOT try next provider — this is the final verdict.
            print(f"\n{'='*60}")
            print(f"  ❌ REJECTED — [{provider}] failed all {max_retries} SMT attempts.")
            print(f"  The BT is unsafe. Switching providers will not fix a logic error.")
            failed = [c for c in outcome["checks"] if not c["passed"]]
            for c in failed:
                print(f"  → [{c['name']}] {c['detail']}")
            print(f"{'='*60}")
            return {
                "status":   "rejected",
                "stage":    "verification",
                "xml":      outcome["xml"],
                "checks":   outcome["checks"],
                "errors":   outcome["errors"],
                "attempts": total_attempts,
                "provider": provider,
            }

        elif outcome["status"] == "api_error":
            # Provider crashed — try the next one in the chain
            print(f"\n  ⚠️  [{provider}] API error: {outcome.get('error_msg', '?')}")
            print(f"  → Falling back to next provider in chain ...")
            continue

    # Every provider in the chain had an API error
    print(f"\n{'='*60}")
    print(f"  ✗ All providers in chain failed with API errors.")
    print(f"{'='*60}")
    return {
        "status":   "error",
        "stage":    "llm",
        "message":  "All LLM providers exhausted (API errors).",
        "attempts": total_attempts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NL2BT-Verify Pipeline")
    parser.add_argument("--input",     type=str, required=True,
                        help="Natural language robot command")
    parser.add_argument("--execute",   action="store_true",
                        help="Execute on robot after verification")
    parser.add_argument("--retries",   type=int, default=MAX_RETRIES,
                        help=f"SMT-guided retries per provider (default: {MAX_RETRIES})")
    parser.add_argument("--providers", nargs="+", default=PROVIDER_CHAIN,
                        choices=["gemini", "openai", "anthropic"],
                        help="Provider fallback chain (used only on API failure)")
    args = parser.parse_args()

    result = run_pipeline(
        nl_input=args.input,
        execute=args.execute,
        max_retries=args.retries,
        provider_chain=args.providers,
    )

    if result["status"] == "success":
        print("\n[Done] Verified Behavior Tree:")
        print(result["xml"])
    else:
        print(f"\n[Failed] Status: {result['status']}")
        sys.exit(1)
