"""
LLM client for Stage 1: Natural Language → XML Behavior Tree.
Default provider: Google Gemini.
"""
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PROMPT_FILE = Path(__file__).parent / "prompts" / "system_prompt.txt"
SYSTEM_PROMPT = PROMPT_FILE.read_text()

GEMINI_MODEL = "gemini-3-flash-preview"


def generate_behavior_tree(nl_input: str, provider: str = "gemini") -> Optional[str]:
    """Generate an XML BT from a natural language command."""
    if provider == "gemini":
        return _generate_gemini(nl_input)
    elif provider == "anthropic":
        return _generate_anthropic(nl_input)
    elif provider == "openai":
        return _generate_openai(nl_input)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'gemini', 'anthropic', or 'openai'.")


def _generate_gemini(nl_input: str) -> Optional[str]:
    import google.genai as genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=nl_input,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=1024,
            temperature=0.0,
        ),
    )
    text = response.text.strip()
    # Strip markdown fences if Gemini wraps output in ```xml ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()


def _generate_anthropic(nl_input: str) -> Optional[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": nl_input}],
    )
    return message.content[0].text.strip()


def _generate_openai(nl_input: str) -> Optional[str]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": nl_input},
        ],
        max_tokens=1024,
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()
