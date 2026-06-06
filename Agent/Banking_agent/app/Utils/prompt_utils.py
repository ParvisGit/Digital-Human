"""
AVA-style prompt utilities: load prompts from .txt files and format with placeholders.
"""
import os
import json
from pathlib import Path
from Banking_agent.app.Utils.prompt_repository import get_prompt

def get_state_config() -> dict:
    """Load state config for placeholder values (bankName, agentName, etc.)."""
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "state_config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"bankName": "GiniBank", "agentName": "GiniBank Assistant"}


def format_prompt_with_placeholders(
    prompt_text: str,
    placeholder_values: dict,
    additional_placeholder_values: dict | None = None,
) -> str:
    """Format the prompt text by replacing placeholders with values from the dictionary."""
    try:
        if additional_placeholder_values:
            placeholder_values = {**placeholder_values, **additional_placeholder_values}
        return prompt_text.format(**placeholder_values)
    except KeyError as e:
        return prompt_text
    except Exception:
        return prompt_text


def load_prompt_from_file(prompt_name: str, placeholder_values: dict | None = None) -> str | None:
    """
    Load prompt from prompts/{prompt_name}.txt and optionally format with placeholders.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    prompt_file_path = project_root / "prompts" / f"{prompt_name}.txt"
    if not prompt_file_path.exists():
        return None
    try:
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            prompt_text = f.read().strip()
        if not prompt_text:
            return None
        if placeholder_values is None:
            placeholder_values = get_state_config()
        return format_prompt_with_placeholders(prompt_text, placeholder_values)
    except Exception:
        return None

def load_prompt(prompt_name: str,
                placeholder_values: dict | None = None
                ) -> str | None:
    prompt_text = get_prompt(prompt_name)
    if not prompt_text:
        return None
    if placeholder_values is None:
        placeholder_values = get_state_config()
    return format_prompt_with_placeholders(
        prompt_text,
        placeholder_values
    )