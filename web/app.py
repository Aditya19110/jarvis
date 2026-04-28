"""
web/app.py — JARVIS FastAPI Backend
Serves the web UI and handles chat + voice endpoints.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add jarvis root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.system_info import get_system_info

app = FastAPI(title="JARVIS API", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ─── Models ───────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    stream: bool = True


class VoiceRequest(BaseModel):
    audio_b64: str  # Base64-encoded WAV audio bytes


class ResetRequest(BaseModel):
    pass


# ─── Startup — load LLM once ──────────────────────────────

_llm = None
_llm_ready = False
_agent = None
_whisper = None  # Loaded on first voice request


@app.on_event("startup")
async def startup_event():
    global _llm, _llm_ready
    # Load in background thread so the server stays responsive
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_llm)


def _load_llm():
    global _llm, _llm_ready, _agent
    from core.llm import get_llm
    from core.agent import JarvisAgent
    _llm = get_llm()
    _agent = JarvisAgent(_llm)
    _llm_ready = True


# ─── Routes ───────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def root():
    index = STATIC_DIR / "index.html"
    return HTMLResponse(content=index.read_text(), status_code=200)


@app.get("/api/status")
async def status():
    """Health check — returns LLM readiness + system stats."""
    info = get_system_info()
    return {
        "llm_ready": _llm_ready,
        "model": "mlx-community/Phi-3-mini-4k-instruct-4bit",
        "system": info,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Chat endpoint — routes through agent (tools + LLM)."""
    if not _llm_ready:
        raise HTTPException(503, "JARVIS is still loading. Please wait.")

    if req.stream:
        async def event_generator():
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def stream_in_thread():
                try:
                    for token in _agent.stream(req.message):
                        loop.call_soon_threadsafe(queue.put_nowait, token)
                except Exception as e:
                    loop.call_soon_threadsafe(queue.put_nowait, f"\n\n⚠️ Error: {e}")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            loop.run_in_executor(None, stream_in_thread)

            while True:
                token = await queue.get()
                if token is None:
                    yield "data: [DONE]\n\n"
                    break
                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _agent.chat, req.message)
        return {"response": response}


@app.post("/api/voice")
async def voice_to_text(req: VoiceRequest):
    """
    Receive base64-encoded audio (webm/opus from browser MediaRecorder),
    convert to wav 16kHz via ffmpeg, then transcribe with Whisper.
    """
    global _whisper
    tmp_webm = None
    tmp_wav  = None
    try:
        import whisper
        import subprocess

        # Load Whisper once and cache it
        if _whisper is None:
            from config import WHISPER_MODEL
            _whisper = whisper.load_model(WHISPER_MODEL)

        audio_bytes = base64.b64decode(req.audio_b64)
        if len(audio_bytes) < 1000:
            return {"transcript": "", "error": "Audio too short — nothing recorded."}

        # Write raw webm bytes to a temp file
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_bytes)
            tmp_webm = f.name

        # Convert webm → wav 16kHz mono via ffmpeg (Whisper's sweet spot)
        tmp_wav = tmp_webm.replace(".webm", ".wav")
        ffmpeg_result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", tmp_webm,
                "-ar", "16000",   # 16kHz sample rate
                "-ac", "1",       # mono
                "-f", "wav",
                tmp_wav,
            ],
            capture_output=True,
            timeout=30,
        )

        if ffmpeg_result.returncode != 0:
            # ffmpeg failed — try passing webm directly to Whisper as fallback
            wav_to_use = tmp_webm
        else:
            wav_to_use = tmp_wav

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: _whisper.transcribe(
                wav_to_use,
                fp16=False,
                language="en",
                temperature=0.0,          # Greedy decode = more accurate
                condition_on_previous_text=False,
            )
        )

        transcript = result["text"].strip()

        # Strip common Whisper hallucinations on silence
        _hallucinations = {
            "thank you.", "thanks.", "thank you for watching.",
            "you", ".", "", "bye.", "bye-bye.", "see you.",
        }
        if transcript.lower() in _hallucinations:
            transcript = ""

        return {"transcript": transcript}

    except Exception as e:
        raise HTTPException(500, f"Voice transcription failed: {e}")
    finally:
        for p in [tmp_webm, tmp_wav]:
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass



@app.post("/api/reset")
async def reset_conversation():
    """Clear JARVIS in-memory conversation (disk history preserved)."""
    if _llm:
        _llm.reset_conversation()
    return {"status": "ok", "message": "Conversation cleared."}


@app.get("/api/history")
async def get_history():
    """Return current session's conversation history."""
    if not _llm:
        return {"history": []}
    return {"history": _llm.history}


@app.get("/api/history/all")
async def get_all_history():
    """Return all saved session summaries from disk."""
    from core.memory import get_all_sessions_summary
    return {"sessions": get_all_sessions_summary()}


@app.get("/api/memory")
async def get_memory():
    """Return current user memory."""
    from core.memory import load_memory
    return load_memory()


@app.patch("/api/memory")
async def update_memory_endpoint(request: Request):
    """Manually update user memory fields."""
    from core.memory import load_memory, save_memory
    data = await request.json()
    mem = load_memory()
    for k, v in data.items():
        if k in mem:
            mem[k] = v
    save_memory(mem)
    return {"status": "ok", "memory": mem}


@app.delete("/api/memory")
async def clear_memory():
    """Reset user memory to defaults."""
    from core.memory import DEFAULT_MEMORY, save_memory
    import copy
    mem = copy.deepcopy(DEFAULT_MEMORY)
    save_memory(mem)
    return {"status": "ok"}


# ─── Entry point ──────────────────────────────────────────

if __name__ == "__main__":
    from config import SERVER_HOST, SERVER_PORT
    uvicorn.run("web.app:app", host=SERVER_HOST, port=SERVER_PORT, reload=False)
