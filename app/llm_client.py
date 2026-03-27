"""
app/llm_client.py
─────────────────────────────────────────────────────────────────────────────
Single LLM client. Uses OpenRouter API (for Railway/cloud deployment).
Falls back to local Ollama if OPENROUTER_API_KEY is not set.

Usage:
    from app.llm_client import llm_complete
    response = llm_complete(system="...", prompt="...", max_tokens=400)
"""

import os, requests, json
from typing import Optional

# ── Config — read at call time so Railway env vars are always picked up ───────
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def llm_complete(system: str, prompt: str, max_tokens: int = 400, temperature: float = 0.4) -> str:
    """
    Complete a prompt using OpenRouter (cloud) or Ollama (local).
    Reads env vars at call time — works correctly on Railway.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if api_key:
        return _openrouter(system, prompt, max_tokens, temperature, api_key)
    else:
        return _ollama(system, prompt, max_tokens, temperature)


def _openrouter(system: str, prompt: str, max_tokens: int, temperature: float, api_key: str = "") -> str:
    """Call OpenRouter API — OpenAI-compatible format."""
    if not api_key:
        api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
    try:
        r = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization":  f"Bearer {api_key}",
                "Content-Type":   "application/json",
                "HTTP-Referer":   "https://github.com/YashashriShiral/RAG_implementation",
                "X-Title":        "Endo Tracker",
            },
            json={
                "model":       model,
                "max_tokens":  max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "system",  "content": system},
                    {"role": "user",    "content": prompt},
                ],
            },
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        import logging
        logging.getLogger("llm_client").warning(f"[OPENROUTER] failed: {e}")
        return ""


def _ollama(system: str, prompt: str, max_tokens: int, temperature: float) -> str:
    """Call local Ollama — fallback when no API key set."""
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/generate"
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        r = requests.post(
            ollama_url,
            json={
                "model":   ollama_model,
                "prompt":  prompt,
                "system":  system,
                "stream":  False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        import logging
        logging.getLogger("llm_client").warning(f"[OLLAMA] failed: {e}")
        return ""
