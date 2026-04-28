"""
core/agent.py — JARVIS Agent Pipeline

input → router → tool OR llm → response

This is the single entry point for ALL requests.
"""
from __future__ import annotations

import re
import subprocess
import time
from typing import Generator

from rich.console import Console

console = Console()

# ── App name mappings for macOS ──────────────────────────────
_APP_MAP = {
    'vscode':        'Visual Studio Code',
    'vs code':       'Visual Studio Code',
    'visual studio': 'Visual Studio Code',
    'terminal':      'Terminal',
    'iterm':         'iTerm',
    'iterm2':        'iTerm',
    'finder':        'Finder',
    'brave':         'Brave Browser',
    'chrome':        'Google Chrome',
    'safari':        'Safari',
    'firefox':       'Firefox',
    'spotify':       'Spotify',
    'notes':         'Notes',
    'activity monitor': 'Activity Monitor',
    'xcode':         'Xcode',
    'cursor':        'Cursor',
    'pycharm':       'PyCharm',
    'slack':         'Slack',
    'discord':       'Discord',
    'zoom':          'zoom.us',
}


# ══════════════════════════════════════════════════════════════
#  TOOLS
# ══════════════════════════════════════════════════════════════

def _open_app(name: str) -> str:
    """Launch a macOS app by name."""
    real = _APP_MAP.get(name.strip().lower(), name.strip())
    result = subprocess.run(['open', '-a', real], capture_output=True, text=True)
    if result.returncode == 0:
        return f"✅ Launched **{real}**."
    return f"❌ Couldn't open **{real}**. Is it installed?\n```\n{result.stderr.strip()}\n```"


def _run_shell(cmd: str) -> str:
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=15
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        combined = out or err or '(no output)'
        return f"```bash\n$ {cmd}\n{combined}\n```"
    except subprocess.TimeoutExpired:
        return f"⏱ Command timed out after 15s: `{cmd}`"
    except Exception as e:
        return f"❌ Error running `{cmd}`: {e}"


def _system_status() -> str:
    """Return rich system status."""
    from skills.system_info import get_system_info
    s = get_system_info()

    lines = [
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| CPU | {s['cpu_percent']}% |",
        f"| RAM | {s['ram_used_gb']} GB / {s['ram_total_gb']} GB ({s['ram_percent']}%) |",
        f"| Disk | {s['disk_percent']}% used |",
    ]
    if s.get('battery'):
        b = s['battery']
        plug = "⚡ charging" if b.get('power_plugged') else "🔋 on battery"
        lines.append(f"| Battery | {b['percent']}% ({plug}) |")

    return "\n".join(lines)


def _list_files(path: str = '.') -> str:
    """List files in a directory."""
    return _run_shell(f'ls -la "{path}"')


def _screenshot() -> str:
    """Take a macOS screenshot."""
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = f'~/Desktop/jarvis_screenshot_{ts}.png'
    return _run_shell(f'screencapture {path}') + f"\nSaved to {path}"


def _mute() -> str:
    return _run_shell("osascript -e 'set volume output muted true'") + "\n🔇 Muted."


def _set_volume(level: str) -> str:
    try:
        lvl = int(level)
        lvl = max(0, min(100, lvl))
        mac_lvl = round(lvl / 10)
        _run_shell(f"osascript -e 'set volume output volume {lvl}'")
        return f"🔊 Volume set to {lvl}%."
    except Exception:
        return "Specify volume as a number 0–100."


def _recall_memory() -> str:
    from core.memory import load_memory, memory_to_context
    mem = load_memory()
    ctx = memory_to_context(mem)
    return f"Here's what I know about you:\n\n{ctx}"


# ══════════════════════════════════════════════════════════════
#  AGENT
# ══════════════════════════════════════════════════════════════

class JarvisAgent:
    """
    The reasoning layer between user input and the LLM.
    
    Pipeline:
      input → router → tool result  (immediate, no LLM needed)
                     → LLM          (for open-ended questions)
    """

    def __init__(self, llm):
        self.llm = llm

    def _dispatch(self, intent: str, match: re.Match | None, text: str) -> str | None:
        """
        Execute the matched intent. Returns tool result string, or None to use LLM.
        """
        if intent == 'llm':
            return None

        if intent == 'open_vscode':
            return _open_app('Visual Studio Code')
        if intent == 'open_terminal':
            return _open_app('Terminal')
        if intent == 'open_finder':
            return _open_app('Finder')
        if intent == 'open_browser':
            return _open_app('Brave Browser')
        if intent == 'open_spotify':
            return _open_app('Spotify')
        if intent == 'open_notes':
            return _open_app('Notes')
        if intent == 'open_activity_monitor':
            return _open_app('Activity Monitor')
        if intent == 'open_app_generic':
            app = match.group(1).strip() if match else text
            return _open_app(app)
        if intent == 'run_shell':
            cmd = match.group(1).strip() if match else ''
            return _run_shell(cmd) if cmd else "No command found. Use: run `your command`"
        if intent == 'system_status':
            return _system_status()
        if intent == 'list_files':
            return _list_files('.')
        if intent == 'screenshot':
            return _screenshot()
        if intent == 'mute_volume':
            return _mute()
        if intent == 'set_volume':
            level = match.group(1) if match else '50'
            return _set_volume(level)
        if intent == 'recall_memory':
            return _recall_memory()
        if intent == 'remember':
            # Let LLM handle this naturally — it'll get saved to memory
            return None

        return None  # Unknown intent → LLM

    def stream(self, user_input: str) -> Generator[str, None, None]:
        """
        Main entry point for streaming responses.
        Tool results: yield as single chunk.
        LLM: yield word-by-word.
        """
        from core.router import route
        intent, match = route(user_input)

        console.print(f"[dim]🧭 Intent: [cyan]{intent}[/]  text=[yellow]{user_input[:50]}[/][/]")

        tool_result = self._dispatch(intent, match, user_input)

        if tool_result is not None:
            # Tool executed — yield result directly
            yield tool_result
        else:
            # Route to LLM
            yield from self.llm.chat_stream(user_input)

    def chat(self, user_input: str) -> str:
        """Non-streaming version (for fallback use)."""
        from core.router import route
        intent, match = route(user_input)
        tool_result = self._dispatch(intent, match, user_input)
        if tool_result is not None:
            return tool_result
        return self.llm.chat(user_input)


# ── Singleton ─────────────────────────────────────────────────
_agent: JarvisAgent | None = None


def get_agent() -> JarvisAgent:
    global _agent
    if _agent is None:
        from core.llm import get_llm
        _agent = JarvisAgent(get_llm())
    return _agent
