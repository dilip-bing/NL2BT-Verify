"""
LLM client for Stage 1: Natural Language → XML Behavior Tree.

Provider fallback chain  : Gemini → GPT-4o → Claude
  If a provider is unavailable (missing key, API error, quota exceeded)
  the next provider in the chain is tried automatically.

Retry-with-feedback      : pipeline.py passes SMT error context on retries
  so the LLM can fix specific violations rather than regenerating blindly.
"""
from __future__ import annotations
import os
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger(__name__)

PROMPT_FILE   = Path(__file__).parent / "prompts" / "system_prompt.txt"
SYSTEM_PROMPT = PROMPT_FILE.read_text()

GEMINI_MODEL    = "gemini-flash-latest"
ANTHROPIC_MODEL = "claude-sonnet-4-5"
OPENAI_MODEL    = "gpt-4o"

# Default fallback order — Gemini first (cheapest), then GPT-4o, then Claude.
DEFAULT_PROVIDER_CHAIN = ["gemini", "openai", "anthropic"]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_behavior_tree(
    nl_input: str,
    provider: str = "gemini",
    smt_feedback: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a single XML BT from a natural language command using one provider.

    Args:
        nl_input:     The user's natural-language robot command.
        provider:     One of "gemini", "openai", "anthropic".
        smt_feedback: Optional SMT rejection message from a previous attempt
                      on the SAME provider. When provided, it is appended to
                      the prompt so the LLM can correct the specific violation.
                      Switching providers is handled by the pipeline, not here.

    Returns:
        XML string, or raises an exception on API / network failure.
    """
    prompt = _build_prompt(nl_input, smt_feedback)
    generators = {
        "gemini":    _generate_gemini,
        "openai":    _generate_openai,
        "anthropic": _generate_anthropic,
    }
    if provider not in generators:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Choose from: {list(generators.keys())}"
        )
    return generators[provider](prompt)


def generate_behavior_tree_with_fallback(
    nl_input: str,
    provider_chain: list[str] = DEFAULT_PROVIDER_CHAIN,
    smt_feedback: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """
    Try providers in order; return the first successful XML BT.

    Fallback order (default): Gemini → GPT-4o → Claude.
    A provider is skipped if:
      - its API key is missing from the environment, OR
      - it raises any exception (quota, network, invalid response, etc.)

    Args:
        nl_input:       The user's natural-language robot command.
        provider_chain: Ordered list of provider names to try.
        smt_feedback:   SMT error context for retry attempts (see above).

    Returns:
        (xml_bt, provider_name) — the XML string and the provider that succeeded.

    Raises:
        RuntimeError if all providers in the chain fail.
    """
    prompt   = _build_prompt(nl_input, smt_feedback)
    last_err = None

    for provider in provider_chain:
        # Skip silently if the API key is not configured
        key_map = {
            "gemini":    "GEMINI_API_KEY",
            "openai":    "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_key = key_map.get(provider, "")
        if env_key and not os.environ.get(env_key):
            log.warning("[LLM] Skipping '%s' — %s not set.", provider, env_key)
            continue

        log.info("[LLM] Trying provider: %s", provider)
        try:
            xml = _dispatch(provider, prompt)
            if xml:
                log.info("[LLM] '%s' succeeded (%d chars).", provider, len(xml))
                return xml, provider
            log.warning("[LLM] '%s' returned empty response.", provider)
        except Exception as exc:
            last_err = exc
            log.warning("[LLM] '%s' failed: %s — trying next provider.", provider, exc)

    raise RuntimeError(
        f"All LLM providers exhausted. Last error: {last_err}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(nl_input: str, smt_feedback: Optional[str]) -> str:
    """
    Combine the user command with optional SMT failure feedback.

    On a retry, the prompt tells the LLM exactly which safety property
    failed and what the bad XML looked like, so it can fix the root cause
    rather than generating the same tree again.
    """
    if not smt_feedback:
        return nl_input

    return (
        f"{nl_input}\n\n"
        f"--- PREVIOUS ATTEMPT REJECTED BY SAFETY VERIFIER ---\n"
        f"{smt_feedback}\n"
        f"--- END OF REJECTION DETAILS ---\n\n"
        f"Please regenerate the behavior tree, fixing ALL of the violations "
        f"listed above. Return only valid XML."
    )


def _dispatch(provider: str, prompt: str) -> Optional[str]:
    """Route a prompt to the correct generator function."""
    if provider == "gemini":
        return _generate_gemini(prompt)
    if provider == "openai":
        return _generate_openai(prompt)
    if provider == "anthropic":
        return _generate_anthropic(prompt)
    raise ValueError(f"Unknown provider: {provider}")


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that some models add despite being told not to."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove opening fence (```xml or ```) and closing fence (```)
        start = 1
        end   = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text  = "\n".join(lines[start:end])
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Provider implementations
# ─────────────────────────────────────────────────────────────────────────────

def _generate_gemini(prompt: str) -> Optional[str]:
    """Call Gemini via REST API directly — no SDK version dependency."""
    import urllib.request
    import json

    api_key = os.environ["GEMINI_API_KEY"]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 0.0,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    text = body["candidates"][0]["content"]["parts"][0]["text"]
    return _strip_fences(text)


def _generate_openai(prompt: str) -> Optional[str]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=1024,
        temperature=0.0,
    )
    return _strip_fences(response.choices[0].message.content)


def _generate_anthropic(prompt: str) -> Optional[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _strip_fences(message.content[0].text)
