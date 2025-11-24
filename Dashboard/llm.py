from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple

from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

class LLMNotConfiguredError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_tokens: int = 4096


def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        return st.secrets.get(name, os.getenv(name, default))  # type: ignore[attr-defined]
    except Exception:
        # st.secrets may be unavailable in some contexts
        return os.getenv(name, default)


class ChatLLM:
    """
    Lightweight wrapper for chat completions with optional streaming using
    Google Gemini via the google-generativeai SDK.

    Usage:
        client = ChatLLM()
        text = client.chat_once(messages)
        for chunk in client.stream_chat(messages):
            ...
    """

    def __init__(self, cfg: Optional[LLMConfig] = None):
        self.cfg = cfg or LLMConfig(
            provider=_get_secret("LLM_PROVIDER", "gemini") or "gemini",
            model=_get_secret("MODEL_ID", "gemini-2.5-flash") or "gemini-2.5-flash",
            temperature=float(_get_secret("TEMPERATURE", "0.2") or 0.2),
            max_tokens=int(_get_secret("MAX_TOKENS", "512") or 512),
        )

        self.provider = (self.cfg.provider or "gemini").lower()
        if self.provider != "gemini":
            raise LLMNotConfiguredError(
                f"Unsupported LLM_PROVIDER '{self.provider}'. Supported: 'gemini'."
            )

        # Lazy init for Gemini model
        self._gemini_model = None

    # ---------------- Gemini helpers ----------------
    def _ensure_gemini(self):
        if self._gemini_model is not None:
            return self._gemini_model
        api_key = _get_secret("GEMINI_API_KEY") or _get_secret("GOOGLE_API_KEY")
        if not api_key:
            raise LLMNotConfiguredError(
                "Missing GEMINI_API_KEY or GOOGLE_API_KEY in st.secrets or environment."
            )
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=api_key)
        except Exception as e:  # pragma: no cover
            raise LLMNotConfiguredError(
                "Gemini SDK not installed. Add 'google-generativeai' to requirements.txt."
            ) from e

        # Optionally pick system instruction from session state
        system_instruction = None
        if "chat_messages" in st.session_state:
            for m in st.session_state.get("chat_messages", []):
                if m.get("role") == "system":
                    system_instruction = m.get("content")
                    break

        self._gemini_model = genai.GenerativeModel(
            model_name=self.cfg.model,
            system_instruction=system_instruction,
            generation_config={
                "temperature": self.cfg.temperature,
                "max_output_tokens": self.cfg.max_tokens,
            },
        )
        return self._gemini_model

    # ---------------- Internal transform ----------------
    @staticmethod
    def _to_gemini_contents(messages: List[Dict[str, str]]) -> Tuple[Optional[str], List[Dict]]:
        """Convert OpenAI-style messages to Gemini contents.
        Returns (system_instruction, contents_list)
        """
        system = None
        contents: List[Dict] = []
        for m in messages:
            role = (m.get("role") or "user").lower()
            text = m.get("content", "")
            if role == "system":
                system = text
                continue
            gemini_role = "user" if role == "user" else "model"
            contents.append({"role": gemini_role, "parts": [text]})
        return system, contents

    # ---------------- Public API ----------------
    def chat_once(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,  # Unused for Gemini
    ) -> str:
        """Return a single completion text for the given messages."""
        if self.provider == "gemini":
            mdl = self._ensure_gemini()
            system, contents = self._to_gemini_contents(messages)
            if system:
                import google.generativeai as genai  # type: ignore

                mdl = genai.GenerativeModel(
                    model_name=model or self.cfg.model,
                    system_instruction=system,
                    generation_config={
                        "temperature": temperature if temperature is not None else self.cfg.temperature,
                        "max_output_tokens": max_tokens if max_tokens is not None else self.cfg.max_tokens,
                    },
                )
            try:
                resp = mdl.generate_content(contents)
                return (getattr(resp, "text", None) or "").strip()
            except Exception as e:
                raise LLMNotConfiguredError(str(e))
        raise LLMNotConfiguredError("No supported provider configured")

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,  # Unused for Gemini
    ) -> Iterator[str]:
        """Yield content chunks for the given messages."""
        if self.provider == "gemini":
            mdl = self._ensure_gemini()
            system, contents = self._to_gemini_contents(messages)
            if system:
                import google.generativeai as genai  # type: ignore

                mdl = genai.GenerativeModel(
                    model_name=model or self.cfg.model,
                    system_instruction=system,
                    generation_config={
                        "temperature": temperature if temperature is not None else self.cfg.temperature,
                        "max_output_tokens": max_tokens if max_tokens is not None else self.cfg.max_tokens,
                    },
                )
            try:
                response = mdl.generate_content(contents, stream=True)
                for chunk in response:
                    txt = getattr(chunk, "text", None)
                    if txt:
                        yield txt
                try:
                    response.resolve()
                except Exception:
                    pass
                return
            except Exception as e:
                raise LLMNotConfiguredError(str(e))
        raise LLMNotConfiguredError("No supported provider configured")

    # ---------------- Utilities ----------------
    @staticmethod
    def trim_history(messages: List[Dict[str, str]], max_messages: int = 16) -> List[Dict[str, str]]:
        if len(messages) <= max_messages:
            return messages
        # Keep system (if present) and last n-1 others
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
        trimmed = (system[:1] if system else []) + others[-(max_messages - (1 if system else 0)) :]
        return trimmed


