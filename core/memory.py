"""
core/memory.py — JARVIS Long-Term Memory & Persistent History

Two storage layers:
1. chat_history.json   — Full conversation logs, persisted across restarts
2. user_memory.json    — Extracted facts about the user (preferences, projects, name, etc.)
                         Automatically updated as JARVIS learns from conversations.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


# ─── Paths ────────────────────────────────────────────────────
def _data_dir() -> Path:
    from config import BASE_DIR
    d = Path(BASE_DIR) / "data"
    d.mkdir(exist_ok=True)
    return d


def _history_path() -> Path:
    return _data_dir() / "chat_history.json"


def _memory_path() -> Path:
    return _data_dir() / "user_memory.json"


# ══════════════════════════════════════════════════════════════
# CHAT HISTORY  —  Save & Load full conversation logs
# ══════════════════════════════════════════════════════════════

def save_conversation(messages: list[dict], session_id: str | None = None) -> None:
    """
    Append a conversation session to chat_history.json.
    Each session is tagged with a timestamp and session ID.
    """
    path = _history_path()

    # Load existing history
    all_sessions: list[dict] = []
    if path.exists():
        try:
            all_sessions = json.loads(path.read_text())
        except Exception:
            all_sessions = []

    session = {
        "session_id": session_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
        "timestamp": datetime.now().isoformat(),
        "messages": messages,
    }

    # Find existing session and update, or append new
    for i, s in enumerate(all_sessions):
        if s.get("session_id") == session["session_id"]:
            all_sessions[i] = session
            break
    else:
        all_sessions.append(session)

    # Keep only last 100 sessions to avoid huge files
    all_sessions = all_sessions[-100:]
    path.write_text(json.dumps(all_sessions, indent=2, ensure_ascii=False))


def load_recent_history(max_turns: int = 20) -> list[dict]:
    """
    Load the most recent N conversation turns from the last session.
    Used to restore context on restart.
    """
    path = _history_path()
    if not path.exists():
        return []

    try:
        all_sessions = json.loads(path.read_text())
        if not all_sessions:
            return []

        # Get messages from the most recent session
        last_session = all_sessions[-1]
        messages = last_session.get("messages", [])

        # Return last max_turns messages (user + assistant pairs)
        return messages[-max_turns:]
    except Exception as e:
        console.print(f"[yellow]⚠ Could not load history: {e}[/]")
        return []


def get_all_sessions_summary() -> list[dict]:
    """Return summary of all saved sessions (id, timestamp, message count)."""
    path = _history_path()
    if not path.exists():
        return []
    try:
        sessions = json.loads(path.read_text())
        return [
            {
                "session_id": s.get("session_id"),
                "timestamp": s.get("timestamp"),
                "message_count": len(s.get("messages", [])),
                "preview": s.get("messages", [{}])[0].get("content", "")[:80] if s.get("messages") else "",
            }
            for s in sessions
        ]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# USER MEMORY  —  Long-term facts about the user
# ══════════════════════════════════════════════════════════════

DEFAULT_MEMORY = {
    "name": "Aditya Kulkarni",
    "role": "AI Engineer",
    "location": None,
    "preferred_language": "Python",
    "projects": [],
    "interests": [],
    "preferences": {},
    "facts": [],
    "last_updated": None,
}


def load_memory() -> dict:
    """Load user memory from disk. Creates default if not exists."""
    path = _memory_path()
    if not path.exists():
        save_memory(DEFAULT_MEMORY.copy())
        return DEFAULT_MEMORY.copy()
    try:
        return json.loads(path.read_text())
    except Exception:
        return DEFAULT_MEMORY.copy()


def save_memory(memory: dict) -> None:
    """Persist user memory to disk."""
    path = _memory_path()
    memory["last_updated"] = datetime.now().isoformat()
    path.write_text(json.dumps(memory, indent=2, ensure_ascii=False))


def update_memory(key: str, value: Any) -> None:
    """Update a single field in user memory."""
    mem = load_memory()
    if key in ("projects", "interests", "facts"):
        # These are lists — append if not already there
        if isinstance(value, list):
            existing = set(mem.get(key, []))
            for item in value:
                if item and item not in existing:
                    mem.setdefault(key, []).append(item)
                    existing.add(item)
        else:
            if value and value not in mem.get(key, []):
                mem.setdefault(key, []).append(value)
    else:
        if value:
            mem[key] = value
    save_memory(mem)


def memory_to_context(memory: dict) -> str:
    """
    Format memory into a compact context block injected into the system prompt.
    """
    lines = ["[USER PROFILE — use this to personalize your responses]"]

    if memory.get("name"):
        lines.append(f"Name: {memory['name']}")
    if memory.get("role"):
        lines.append(f"Role: {memory['role']}")
    if memory.get("location"):
        lines.append(f"Location: {memory['location']}")
    if memory.get("preferred_language"):
        lines.append(f"Preferred coding language: {memory['preferred_language']}")
    if memory.get("projects"):
        lines.append(f"Active projects: {', '.join(memory['projects'][-5:])}")
    if memory.get("interests"):
        lines.append(f"Interests: {', '.join(memory['interests'][-8:])}")
    if memory.get("preferences"):
        for k, v in list(memory["preferences"].items())[-5:]:
            lines.append(f"Preference — {k}: {v}")
    if memory.get("facts"):
        lines.append("Known facts about the user:")
        for fact in memory["facts"][-10:]:
            lines.append(f"  • {fact}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# MEMORY EXTRACTOR  —  Pull facts from a conversation turn
# ══════════════════════════════════════════════════════════════

_EXTRACT_PROMPT = """You are a data extractor. Your task is to extract NEW factual information about the user from their message.

RULES:
1. ONLY extract clear, explicit facts. No guesses.
2. DO NOT copy the descriptions below into your output. 
3. Return a JSON object with ONLY the fields that have new information.

FIELDS:
- name: The user's actual name.
- location: City or country.
- preferred_language: Their coding language preference.
- projects: A list of specific project names.
- interests: A list of topics they enjoy.
- facts: Any other concrete facts.
- preferences: Specific settings or styles they like.

User message: "{message}"

Return ONLY the JSON object. If nothing new is found, return {{}}.
"""


def extract_facts_from_message(user_message: str, model=None, tokenizer=None) -> dict:
    """
    Use the LLM to extract facts about the user from their message.
    Runs after each user turn, updating memory automatically.
    """
    if model is None or tokenizer is None:
        return {}

    try:
        from mlx_lm import generate  # type: ignore
        from mlx_lm.sample_utils import make_sampler  # type: ignore

        prompt_text = _EXTRACT_PROMPT.format(message=user_message[:500])

        # Use a simple prompt (no chat template — just raw extraction)
        sampler = make_sampler(temp=0.0)  # Greedy for JSON extraction
        raw = generate(
            model, tokenizer,
            prompt=prompt_text,
            max_tokens=300,
            sampler=sampler,
        )

        # Extract JSON from response
        raw = raw.strip()
        # Find JSON object in response
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data
        return {}
    except Exception as e:
        return {}


def apply_extracted_facts(facts: dict) -> None:
    """Merge extracted facts into user memory."""
    if not facts:
        return

    for key in ("name", "location", "preferred_language"):
        if facts.get(key):
            update_memory(key, facts[key])

    for key in ("projects", "interests", "facts"):
        if facts.get(key):
            update_memory(key, facts[key])

    if facts.get("preferences"):
        mem = load_memory()
        prefs = mem.get("preferences", {})
        prefs.update(facts["preferences"])
        mem["preferences"] = prefs
        save_memory(mem)
