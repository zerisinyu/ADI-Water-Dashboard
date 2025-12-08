from __future__ import annotations

import os
from pathlib import Path
import tomllib
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

class LLMNotConfiguredError(RuntimeError):
    pass


def build_data_context_prompt() -> str:
    """
    Build a context string from current dashboard state and data.
    This is injected into the system prompt for data-aware responses.
    """
    context_parts = []
    
    # Get filters
    country = st.session_state.get("selected_country", "All")
    zone = st.session_state.get("selected_zone", "All")
    year = st.session_state.get("selected_year", "All")
    month = st.session_state.get("selected_month", "All")
    
    context_parts.append(f"Current filters: Country={country}, Zone={zone}, Year={year}, Month={month}")
    
    # Get cached data insights if available (from exec page)
    if "exec_insights_cache" in st.session_state:
        insights = st.session_state["exec_insights_cache"]
        
        if "overall_score" in insights:
            context_parts.append(f"Overall Performance Score: {insights['overall_score']:.0f}/100")
        
        if "collection_efficiency" in insights:
            context_parts.append(f"Collection Efficiency: {insights['collection_efficiency']:.1f}%")
        
        if "nrw_percent" in insights:
            context_parts.append(f"Non-Revenue Water (NRW): {insights['nrw_percent']:.1f}%")
        
        if "service_hours" in insights:
            context_parts.append(f"Average Service Hours: {insights['service_hours']:.1f} hours/day")
        
        if "anomalies" in insights and insights["anomalies"]:
            anom_text = "; ".join([f"{a['metric']} changed {a['change_pct']:+.1f}%" for a in insights["anomalies"][:2]])
            context_parts.append(f"Recent Anomalies: {anom_text}")
        
        if "zones" in insights and insights["zones"]:
            zone_summary = []
            for z, metrics in list(insights["zones"].items())[:3]:
                zone_summary.append(f"{z} (Coll: {metrics.get('collection_efficiency', 0):.0f}%)")
            context_parts.append(f"Zone Performance: {', '.join(zone_summary)}")
    
    if context_parts:
        return "\n\nCurrent Dashboard Data Context:\n" + "\n".join(context_parts)
    else:
        return ""


@dataclass
class LLMConfig:
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_tokens: int = 4096


_local_secrets_cache: Optional[Dict[str, Any]] = None  # type: ignore[name-defined]


def _load_local_secrets() -> Optional[Dict[str, Any]]:
    """Load secrets from Dashboard/.streamlit/secrets.toml if st.secrets is empty."""
    global _local_secrets_cache
    if _local_secrets_cache is not None:
        return _local_secrets_cache
    secrets_path = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        try:
            data = tomllib.loads(secrets_path.read_text())
            _local_secrets_cache = data
            return data
        except Exception:
            _local_secrets_cache = {}
            return _local_secrets_cache
    return None


def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Fetch a secret from st.secrets, dashboard-local secrets, or env vars."""
    try:
        val = st.secrets.get(name)  # type: ignore[attr-defined]
        if val not in (None, ""):
            return val
        # Namespaced under [llm] in st.secrets
        llm_secrets = getattr(st.secrets, "get", lambda *_: None)("llm")  # type: ignore[attr-defined]
        if isinstance(llm_secrets, dict):
            val = llm_secrets.get(name)
            if val not in (None, ""):
                return val
    except Exception:
        pass

    local = _load_local_secrets() or {}
    if name in local and local.get(name) not in (None, ""):
        return local.get(name)  # type: ignore[return-value]
    if "llm" in local and isinstance(local["llm"], dict):
        val = local["llm"].get(name)
        if val not in (None, ""):
            return val  # type: ignore[return-value]

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
        inject_context: bool = True,
    ) -> str:
        """Return a single completion text for the given messages."""
        # Inject data context if requested
        if inject_context:
            messages = self._inject_data_context(messages)
        
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
        inject_context: bool = True,
    ) -> Iterator[str]:
        """Yield content chunks for the given messages."""
        # Inject data context if requested
        if inject_context:
            messages = self._inject_data_context(messages)
        
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
            # Attempt streaming; handle StopIteration (SDK may exhaust immediately)
            response = None
            try:
                response = mdl.generate_content(contents, stream=True)
            except StopIteration:
                response = None
            except Exception as e:
                # Bubble up other errors
                raise LLMNotConfiguredError(str(e))

            yielded_any = False
            if response is not None:
                try:
                    for chunk in response:
                        # Check for safety blocks in streaming chunks
                        if hasattr(chunk, 'candidates') and chunk.candidates:
                            finish_reason = getattr(chunk.candidates[0], 'finish_reason', None)
                            if finish_reason == 3:  # SAFETY
                                yield "I apologize, but I cannot generate that response due to safety guidelines. Please try rephrasing your question."
                                yielded_any = True
                                return
                        
                        # Some SDK versions expose text differently; fallback to candidates/parts
                        txt = getattr(chunk, "text", None)
                        if not txt:
                            try:
                                cands = getattr(chunk, "candidates", []) or []
                                if cands:
                                    parts = getattr(cands[0], "content", None)
                                    if parts and getattr(parts, "parts", None):
                                        txt = "".join(getattr(p, "text", "") for p in parts.parts)
                            except Exception:
                                txt = None
                        if txt:
                            yielded_any = True
                            yield txt
                    try:
                        response.resolve()
                    except Exception:
                        pass
                except StopIteration:
                    # Gracefully end stream
                    pass
                except Exception as e:
                    # Fall back below
                    pass

            # Fallback to non-streaming if nothing was yielded
            if not yielded_any:
                try:
                    non_stream = mdl.generate_content(contents)
                    # Check finish_reason before accessing text
                    if hasattr(non_stream, 'candidates') and non_stream.candidates:
                        candidate = non_stream.candidates[0]
                        finish_reason = getattr(candidate, 'finish_reason', None)
                        
                        # finish_reason: 1=STOP (normal), 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION, 5=OTHER
                        if finish_reason == 3:  # SAFETY
                            yield "I apologize, but I cannot generate that response due to safety guidelines. Please try rephrasing your question."
                            return
                        elif finish_reason == 4:  # RECITATION
                            yield "I cannot provide that response. Please ask a different question."
                            return
                        elif finish_reason in [2, 5]:  # MAX_TOKENS or OTHER
                            yield "I encountered an issue generating the response. Please try again with a simpler question."
                            return
                    
                    # Try to get text normally
                    text = (getattr(non_stream, "text", None) or "").strip()
                    if text:
                        yield text
                        return
                    # No content at all; provide feedback
                    yield "I'm sorry, I couldn't generate a response. Please try asking your question differently."
                    return
                except Exception as e:
                    # Provide user-friendly error message
                    error_msg = str(e).lower()
                    if "safety" in error_msg or "finish_reason" in error_msg:
                        yield "I apologize, but I cannot provide a response to that question. Please try rephrasing it."
                    else:
                        yield f"I encountered an error: {str(e)[:100]}. Please try again."
                    return
            return
        raise LLMNotConfiguredError("No supported provider configured")

    # ---------------- Utilities ----------------
    @staticmethod
    def _inject_data_context(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Inject current data context into system message."""
        context = build_data_context_prompt()
        
        if not context:
            return messages
        
        # Find system message and append context
        modified = []
        system_found = False
        
        for msg in messages:
            if msg.get("role") == "system" and not system_found:
                modified.append({
                    "role": "system",
                    "content": msg.get("content", "") + context
                })
                system_found = True
            else:
                modified.append(msg)
        
        return modified
    
    @staticmethod
    def trim_history(messages: List[Dict[str, str]], max_messages: int = 16) -> List[Dict[str, str]]:
        if len(messages) <= max_messages:
            return messages
        # Keep system (if present) and last n-1 others
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
        trimmed = (system[:1] if system else []) + others[-(max_messages - (1 if system else 0)) :]
        return trimmed
