"""
AVA-style agent runnables: create agents from config using ChatPromptTemplate + bind_tools.
"""
import json
import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from Banking_agent.app.Utils.prompt_utils import load_prompt_from_file, get_state_config, load_prompt
from Banking_agent.app.Utils.tool_registry import TOOL_REGISTRY

def create_llm(model_provider: str, model_name: str) -> ChatGoogleGenerativeAI:
    """Create LLM based on provider. Banking uses Google/Gemini."""
    if model_provider.lower() == "google":
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            project="digital-human-478009",
            location="us-central1",
        )
    raise ValueError(f"Unsupported model provider: {model_provider}")


def create_agent_runnables(config: dict, tool_registry: dict) -> dict:
    """
    Create agent runnables from config (AVA-style).
    Each agent: ChatPromptTemplate(system + messages) | llm.bind_tools(tools).
    """
    agent_runnables = {}
    placeholder_values = get_state_config()

    for agent_cfg in config.get("agents", []):
        agent_name = agent_cfg.get("name", "")
        prompt_name = agent_cfg.get("prompt_name", "")
        model = agent_cfg.get("model", "gemini-2.5-flash")
        model_provider = agent_cfg.get("model_provider", "google")

        # Load prompt from file
        # prompt_text = load_prompt_from_file(prompt_name, placeholder_values)
        prompt_text = load_prompt(agent_name,placeholder_values)
        if not prompt_text:
            prompt_text = agent_cfg.get("prompt", "")
        if not prompt_text or prompt_text == "fallback":
            raise ValueError(f"No prompt found for agent {agent_name}")

        # Build delegate tools (to_<agent_name>)
        agent_descriptions = {
            a.get("name", ""): a.get("description", "No description")
            for a in config.get("agents", [])
        }
        available_agents = []
        for target in agent_cfg.get("agents", []):
            desc = agent_descriptions.get(target, "No description")
            available_agents.append(
                _make_delegate_tool(target, desc)
            )

        # Build tool list
        available_tools = [
            tool_registry[t] for t in agent_cfg.get("tools", [])
            if t in tool_registry
        ]

        llm = create_llm(model_provider, model)
        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_text),
            ("placeholder", "{messages}"),
        ])
        runnable = agent_prompt | llm.bind_tools(available_agents + available_tools)
        agent_runnables[agent_name] = runnable

    return agent_runnables


def _make_delegate_tool(agent_name: str, description: str):
    """Create a to_<agent_name> tool for handoff (AVA-style)."""
    from langchain_core.tools import Tool
    from pydantic import BaseModel, Field

    def delegate_wrapped(tool_input: dict | str):
        return f"Delegating to {agent_name}"

    if agent_name == "authentication_agent":
        class AuthDelegateInput(BaseModel):
            customer_name: str = Field(default="", description="Customer full name (e.g., Joshua Hall)")
            phone_number: str = Field(default="", description="Customer phone number for verification")
            message: str = Field(default="", description="User message or customer name to pass")

        return Tool(
            name=f"to_{agent_name}",
            description=f"Delegate to {agent_name}. {description}. Pass customer_name and phone_number for identity verification.",
            func=delegate_wrapped,
            args_schema=AuthDelegateInput,
        )

    if agent_name == "balance_transactions_agent":
        class BalanceDelegateInput(BaseModel):
            customer_name: str = Field(default="", description="Customer full name (e.g., Joshua Hall)")
            message: str = Field(default="", description="User message or customer name to pass")

        return Tool(
            name=f"to_{agent_name}",
            description=f"Delegate to {agent_name}. {description}. Pass customer_name and message with the customer's name.",
            func=delegate_wrapped,
            args_schema=BalanceDelegateInput,
        )

    if agent_name == "fraud_detection_agent":
        class FraudDelegateInput(BaseModel):
            customer_name: str = Field(default="", description="Verified customer full name")
            message: str = Field(default="", description="User message describing the fraud concern")

        return Tool(
            name=f"to_{agent_name}",
            description=f"Delegate to {agent_name}. {description}. Pass verified customer_name and the fraud-related message.",
            func=delegate_wrapped,
            args_schema=FraudDelegateInput,
        )

    return Tool(
        name=f"to_{agent_name}",
        description=f"Delegate to {agent_name}. {description}. Pass the user's message and context in the argument.",
        func=delegate_wrapped,
    )


def load_config() -> dict:
    """Load agent config from config/config.json."""
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

_config = load_config()
agent_runnables = create_agent_runnables(_config, TOOL_REGISTRY)
