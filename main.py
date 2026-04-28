"""
main.py — JARVIS Entry Point
Run this to start JARVIS. Opens the web server on http://localhost:8000
"""
from __future__ import annotations

import os
import sys
import webbrowser
import threading
import time

# Make sure `jarvis/` is on the path so all imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def print_banner():
    banner = Text()
    banner.append("\n  ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗\n", style="bold cyan")
    banner.append("  ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝\n", style="bold cyan")
    banner.append("  ██║███████║██████╔╝██║   ██║██║███████╗\n", style="bold blue")
    banner.append("  ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║\n", style="bold blue")
    banner.append("  ██║██║  ██║██║  ██║ ╚████╔╝ ██║███████║\n", style="bold cyan")
    banner.append("  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝\n", style="bold cyan")
    banner.append("\n  Just A Rather Very Intelligent System\n", style="dim")
    banner.append("  Local AI · Phi-3-mini · Apple Silicon · 100% Offline\n", style="dim")

    console.print(Panel(banner, border_style="cyan", padding=(0, 2)))


def open_browser_delayed(url: str, delay: float = 3.0):
    """Open the browser after a short delay so the server is ready."""
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()


def main():
    print_banner()

    from config import SERVER_HOST, SERVER_PORT
    url = f"http://localhost:{SERVER_PORT}"

    console.print(f"\n[bold cyan]Starting JARVIS server on[/] [underline]{url}[/]")
    console.print("[dim]  The LLM will load in the background. UI will show 'Loading' until ready.[/]\n")

    # Open browser automatically
    open_browser_delayed(url, delay=2.0)

    import uvicorn
    uvicorn.run(
        "web.app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="warning", 
    )


if __name__ == "__main__":
    main()
