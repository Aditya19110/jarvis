"""
core/router.py — JARVIS Intent Router

Intercepts user input BEFORE the LLM.
Pattern-matched intents go straight to tools.
Everything else falls through to the LLM.
"""
from __future__ import annotations
import re

_PATTERNS: list[tuple[str, str]] = [
    (r'\bopen\s+(vs\s*code|vscode|visual\s+studio\s+code)\b',     'open_vscode'),
    (r'\bopen\s+(terminal|iterm2?)\b',                             'open_terminal'),
    (r'\bopen\s+(finder)\b',                                       'open_finder'),
    (r'\bopen\s+(brave|chrome|safari|firefox|browser)\b',          'open_browser'),
    (r'\bopen\s+(spotify)\b',                                      'open_spotify'),
    (r'\bopen\s+(notes|apple notes)\b',                            'open_notes'),
    (r'\bopen\s+(activity monitor)\b',                             'open_activity_monitor'),
    (r'\bopen\s+([a-zA-Z0-9 ]+)',                                  'open_app_generic'),
    (r'(?:run|execute|shell)\s+[`\'"](.+?)[`\'"]',                 'run_shell'),
    (r'(?:run|execute)\s+the\s+command[:\s]+(.+)',                 'run_shell'),
    (r'\b(system\s+status|sys\s+status|sysinfo)\b',               'system_status'),
    (r'\b(cpu|processor)\s*(usage|percent|load|status)?\b',        'system_status'),
    (r'\b(ram|memory)\s*(usage|status)?\b',                        'system_status'),
    (r'\b(battery|charging)\s*(status|level|percent)?\b',          'system_status'),
    (r'\b(disk|storage)\s*(usage|space|status)?\b',                'system_status'),
    (r'\blist\s+(?:files?|dir(?:ectory)?)\b',                      'list_files'),
    (r'\bshow\s+(?:files?|dir(?:ectory)?)\b',                      'list_files'),
    (r'\bls\b',                                                    'list_files'),
    (r'\b(?:remember|note|keep in mind|store)\s+that\b',           'remember'),
    (r'\bwhat\s+(?:do you know|did i tell|have i said)\b',         'recall_memory'),
    (r'\btake\s+(?:a\s+)?screenshot\b',                            'screenshot'),
    (r'\b(?:mute|silence)\b',                                      'mute_volume'),
    (r'\bvolume\s+(up|down|\d+)\b',                                'set_volume'),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), intent) for p, intent in _PATTERNS]


def route(text: str) -> tuple[str, re.Match | None]:
    """
    Returns (intent, match) or ('llm', None) if no pattern matches.
    """
    for pattern, intent in _COMPILED:
        m = pattern.search(text)
        if m:
            return intent, m
    return 'llm', None
