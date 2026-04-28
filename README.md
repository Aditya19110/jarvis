# JARVIS
**Just A Rather Very Intelligent System**

![Apple Silicon](https://img.shields.io/badge/Apple%20Silicon-Optimized-black?logo=apple)
![Local AI](https://img.shields.io/badge/Local%20AI-100%25%20Offline-green)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)

JARVIS is a local, autonomous coding assistant and agent powered by Phi-3-mini running natively on Apple Silicon. Designed as a privacy-first, 100% offline alternative to cloud-based AI, JARVIS provides a professional-grade web interface and system-level task execution capabilities.

## Features

- **Local LLM Optimization**: Runs the Phi-3-mini model natively on Apple Silicon using `mlx-lm` for incredibly fast inference.
- **Professional Web UI**: A beautiful, ChatGPT-style web interface featuring high-contrast code blocks, accurate syntax highlighting, and easy "Copy" functionality.
- **Autonomous Agent Capabilities**: Includes an intent-based command router that intercepts user inputs to execute system tasks (e.g., launching apps, running shell commands, fetching system diagnostics).
- **Persistent Memory**: Seamlessly saves and loads your conversation history, allowing you to pick up exactly where you left off.
- **100% Offline & Private**: Your data, code, and conversations never leave your machine.

## Getting Started

### Prerequisites
- macOS on Apple Silicon (M1/M2/M3/M4)
- Python 3.9 or higher

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Aditya19110/jarvis.git
   cd jarvis
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   cd jarvis
   pip install -r requirements.txt
   ```

## Usage

To launch the JARVIS server and web interface, simply run:

```bash
python main.py
```

This will initialize the server and automatically open your default browser to `http://localhost:8000`. The LLM will load in the background, and the UI will indicate when it is fully ready to assist you.

## Project Structure

- `jarvis/main.py`: The entry point for launching the server and UI.
- `jarvis/web/`: Contains the FastAPI server, HTML, CSS, and JS for the web interface.
- `jarvis/core/`: The core logic, including the LLM initialization (`llm.py`), conversation memory (`memory.py`), and system prompts.
- `jarvis/skills/` & `jarvis/models/`: Agentic capabilities and intent routing definitions.
- `jarvis/data/`: Stores persistent application data such as `chat_history.json`.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
