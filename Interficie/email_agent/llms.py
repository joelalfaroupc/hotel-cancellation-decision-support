from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

from email_agent.schemas import EmailDraft


OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or None
OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME") or "gpt-4o-mini"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def get_openai_llm():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required to compose email")

    openai_params = {
        "model": OPENAI_MODEL_NAME,
        "api_key": OPENAI_API_KEY,
    }
    if OPENAI_BASE_URL:
        openai_params["base_url"] = OPENAI_BASE_URL
    return ChatOpenAI(**openai_params)


def get_email_draft_llm():
    return get_openai_llm().with_structured_output(EmailDraft, method="json_mode")
