"""
core/llm.py — JARVIS Brain
- Loads Phi-3-mini-4bit via MLX-LM 0.31.x
- Persists conversation history across restarts
- Extracts user facts and injects memory into every system prompt
"""
from __future__ import annotations

import sys
import time
import threading
from typing import Generator

from rich.console import Console

console = Console()
_STOP_STRINGS = [
    "<|end|>", "<|endoftext|>", "<|assistant|>",
    "</s>", "<|im_end|>", "<|eot_id|>",
]

def _clean(text_or_obj) -> str:
    # Handle GenerationResponse objects from mlx-lm
    text = text_or_obj
    if hasattr(text_or_obj, "text"):
        text = text_or_obj.text
    
    if not isinstance(text, str):
        text = str(text)

    for tok in _STOP_STRINGS:
        text = text.replace(tok, "")
    return text


class JarvisLLM:

    def __init__(self, model_name: str, max_tokens: int = 512, temperature: float = 0.7):
        self.model_name  = model_name
        self.max_tokens  = max_tokens
        self.temperature = temperature
        self.model       = None
        self.tokenizer   = None
        self._sampler    = None
        self._conversation_history: list[dict] = []
        self._session_id = time.strftime("%Y%m%d_%H%M%S")
        self._load_model()
        self._restore_history()

    def _load_model(self):
        console.print(f"[bold cyan]⚡ JARVIS:[/] Loading model [yellow]{self.model_name}[/] …")
        t0 = time.time()
        try:
            from mlx_lm import load  # type: ignore
        except ImportError:
            console.print("[red]mlx-lm not installed. Run: pip install mlx-lm[/]")
            sys.exit(1)

        self.model, self.tokenizer = load(self.model_name)

        try:
            from mlx_lm.sample_utils import make_sampler  # type: ignore
            self._sampler = make_sampler(temp=self.temperature)
        except ImportError:
            self._sampler = None

        console.print(f"Model ready[/] in [cyan]{time.time() - t0:.1f}s[/]")

    def _restore_history(self):
        """Load last session's history from disk on startup."""
        from core.memory import load_recent_history
        history = load_recent_history(max_turns=10)  # Keep context tight
        if history:
            _bad_openers = (
                "hello sir", "certainly!", "of course!", "absolutely!",
                "sure!", "great question", "i'm glad", "i am glad",
                "i'd be happy", "i would be happy",
            )
            def _is_clean(msg: dict) -> bool:
                if msg.get("role") != "assistant":
                    return True  # always keep user messages
                content_lower = msg.get("content", "").lower().strip()
                return not any(content_lower.startswith(p) for p in _bad_openers)

            history = [m for m in history if _is_clean(m)]
            self._conversation_history = history
            console.print(f"[cyan]📂 Restored {len(history)} clean messages from last session[/]")
        else:
            console.print("[dim]📂 No previous history found — starting fresh[/]")

    def _persist_history(self):
        """Save conversation history to disk (runs in background thread)."""
        def _save():
            try:
                from core.memory import save_conversation
                save_conversation(self._conversation_history, self._session_id)
            except Exception as e:
                pass  # Non-critical
        threading.Thread(target=_save, daemon=True).start()

    def _extract_and_learn(self, user_message: str):
        """Background: extract facts from user message and update memory."""
        def _learn():
            try:
                from core.memory import extract_facts_from_message, apply_extracted_facts
                facts = extract_facts_from_message(user_message, self.model, self.tokenizer)
                if facts:
                    apply_extracted_facts(facts)
                    console.print(f"[dim green]🧠 Memory updated: {list(facts.keys())}[/]")
            except Exception:
                pass
        threading.Thread(target=_learn, daemon=True).start()

    def _get_system_prompt(self) -> str:
        """Build system prompt with injected user memory."""
        from config import JARVIS_SYSTEM_PROMPT
        try:
            from core.memory import load_memory, memory_to_context
            memory = load_memory()
            memory_context = memory_to_context(memory)
            return f"{JARVIS_SYSTEM_PROMPT}\n\n{memory_context}"
        except Exception:
            return JARVIS_SYSTEM_PROMPT

    def _build_messages(self, user_message: str) -> list[dict]:
        """Append user message to history and return full message list."""
        self._conversation_history.append({"role": "user", "content": user_message})
        return [{"role": "system", "content": self._get_system_prompt()}] + self._conversation_history

    def _messages_to_prompt(self, messages: list[dict]) -> str:
        if hasattr(self.tokenizer, "apply_chat_template"):
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        prompt = ""
        for msg in messages:
            tag = {"system": "<|system|>", "user": "<|user|>", "assistant": "<|assistant|>"}.get(msg["role"], "<|user|>")
            prompt += f"{tag}\n{msg['content']}<|end|>\n"
        return prompt + "<|assistant|>\n"

    def _generate(self, prompt: str) -> str:
        """Call mlx-lm generate with sampler-based temperature (0.31.x API)."""
        from mlx_lm import generate  # type: ignore

        kwargs: dict = {"max_tokens": self.max_tokens}
        if self._sampler is not None:
            kwargs["sampler"] = self._sampler

        response = generate(self.model, self.tokenizer, prompt=prompt, **kwargs)
        return _clean(response)

    def chat(self, user_message: str) -> str:
        """Non-streaming: get full response, save history, learn from message."""
        messages = self._build_messages(user_message)
        prompt   = self._messages_to_prompt(messages)
        response = self._generate(prompt)

        self._conversation_history.append({"role": "assistant", "content": response})
        self._persist_history()
        self._extract_and_learn(user_message)  # Background learning
        return response

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        """
        Stream tokens directly from MLX as they are generated.
        Saves history + learns from user message in background.
        """
        messages = self._build_messages(user_message)
        prompt   = self._messages_to_prompt(messages)

        from mlx_lm import stream_generate  # type: ignore

        kwargs: dict = {"max_tokens": self.max_tokens}
        if self._sampler is not None:
            kwargs["sampler"] = self._sampler

        full_response = ""
        for response in stream_generate(self.model, self.tokenizer, prompt=prompt, **kwargs):
            token = _clean(response)
            if token:
                full_response += token
                yield token

        if full_response:
            self._conversation_history.append({"role": "assistant", "content": full_response})
            self._persist_history()           # Save to disk
            self._extract_and_learn(user_message)   # Learn from user

    def reset_conversation(self):
        """Clear in-memory history (doesn't delete disk history)."""
        self._conversation_history = []
        self._session_id = time.strftime("%Y%m%d_%H%M%S")  # New session
        console.print("[cyan]🔄 Conversation cleared. Starting new session.[/]")

    @property
    def history(self) -> list[dict]:
        return self._conversation_history.copy()

_jarvis_llm: JarvisLLM | None = None

def get_llm() -> JarvisLLM:
    global _jarvis_llm
    if _jarvis_llm is None:
        from config import LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE
        _jarvis_llm = JarvisLLM(LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE)
    return _jarvis_llm