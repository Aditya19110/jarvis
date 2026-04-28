"""
core/stt.py — Speech-to-Text via Whisper
Records audio from the microphone and transcribes it locally.
"""
from __future__ import annotations

import io
import threading
import time
import wave

import numpy as np
import sounddevice as sd
import whisper
from rich.console import Console

console = Console()

_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from config import WHISPER_MODEL
        console.print(f"[cyan]🎙️ Loading Whisper [{WHISPER_MODEL}] …[/]")
        _whisper_model = whisper.load_model(WHISPER_MODEL)
        console.print("[green]✅ Whisper ready[/]")
    return _whisper_model


# ─── Recording ────────────────────────────────────────────


def record_audio(seconds: int | None = None) -> np.ndarray:
    """
    Record audio from the default microphone.
    Returns a float32 numpy array at 16kHz (Whisper's expected sample rate).
    """
    from config import AUDIO_SAMPLE_RATE, AUDIO_RECORD_SECONDS

    duration = seconds or AUDIO_RECORD_SECONDS
    sample_rate = AUDIO_SAMPLE_RATE

    console.print(f"[bold yellow]🎤 Listening for {duration}s …[/]")

    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()  # Block until done
    return audio.flatten()


def record_until_silence(
    silence_threshold: float = 0.01,
    silence_duration: float = 1.5,
    max_duration: float = 10.0,
) -> np.ndarray:
    """
    Record until the user stops speaking (auto-stops on silence).
    More natural than fixed-duration recording.
    """
    from config import AUDIO_SAMPLE_RATE

    sample_rate = AUDIO_SAMPLE_RATE
    chunk_size = int(sample_rate * 0.1)  # 100ms chunks

    frames: list[np.ndarray] = []
    silence_frames = 0
    silence_needed = int(silence_duration / 0.1)
    max_frames = int(max_duration / 0.1)

    console.print("[bold yellow]🎤 Listening … (speak now)[/]")

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        while len(frames) < max_frames:
            chunk, _ = stream.read(chunk_size)
            frames.append(chunk.flatten())
            volume = np.abs(chunk).mean()

            if len(frames) > 5:  # Give 500ms buffer before checking silence
                if volume < silence_threshold:
                    silence_frames += 1
                    if silence_frames >= silence_needed:
                        console.print("[dim]🔇 Silence detected — processing …[/]")
                        break
                else:
                    silence_frames = 0

    return np.concatenate(frames)


# ─── Transcription ────────────────────────────────────────


def transcribe(audio: np.ndarray) -> str:
    """Transcribe a numpy audio array using Whisper."""
    model = _get_whisper()
    result = model.transcribe(audio, fp16=False, language="en")
    text = result["text"].strip()
    console.print(f"[bold magenta]👤 You said:[/] {text}")
    return text


def listen_and_transcribe(auto_silence: bool = True) -> str:
    """
    High-level: record from mic → transcribe → return text.
    Set auto_silence=True for smart silence detection (default).
    """
    if auto_silence:
        audio = record_until_silence()
    else:
        audio = record_audio()
    return transcribe(audio)


# ─── Quick test ────────────────────────────────────────────

if __name__ == "__main__":
    text = listen_and_transcribe()
    print(f"\nTranscription: {text}")
