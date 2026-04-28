"""
JARVIS Configuration
All settings live here. Edit this file to customize your JARVIS.
"""
import os

# ─── LLM ────────────────────────────────────────────────────
# 4-bit quantized Phi-3-mini — only ~2GB RAM, runs on Apple Silicon MPS
LLM_MODEL = "mlx-community/Phi-3-mini-4k-instruct-4bit"
LLM_MAX_TOKENS = 1024      # Plenty of room for code
LLM_TEMPERATURE = 0.2     # Very focused responses

# ─── Whisper STT ────────────────────────────────────────────
# "small" is significantly more accurate than "base" for noisy/accented audio
WHISPER_MODEL = "small"
AUDIO_SAMPLE_RATE = 16000   # Hz  (Whisper expects 16k)
AUDIO_RECORD_SECONDS = 6    # Max seconds to record per utterance

# ─── Server ─────────────────────────────────────────────────
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# ─── JARVIS Personality ─────────────────────────────────────
JARVIS_SYSTEM_PROMPT = """You are JARVIS. A direct, technical interface.
Built by Aditya Kulkarni. No internet. No cloud. No fluff.

EXECUTION RULES:
- NO greetings. NO "Hello". NO "Sir". NO "Aditya".
- NO preamble. NO "Certainly", "Here is your code", etc.
- If the user asks for code, start the message with the code block.
- Be extremely brief. 1 sentence max for non-code answers.
- Use a dry, professional, engineering tone.

CODE FORMAT:
```[language]
[code]
```

IDENTITY: You are a local MLX implementation on Apple Silicon. Not a chatbot."""

# ─── Paths ──────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
