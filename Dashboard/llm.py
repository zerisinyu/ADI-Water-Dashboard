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

    # MajiBot's "read on today" — the plain-language daily briefing the exec page
    # used to show in an expander. Folding it into the chat context lets MajiBot
    # open with today's read when asked.
    daily_reading = st.session_state.get("daily_reading")
    if daily_reading:
        context_parts.append(f"Today's read (MajiBot's daily briefing): {daily_reading}")

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
    base_url: Optional[str] = None


# Built-in OpenAI-compatible providers. Adding a new provider is just a new
# entry here (or, at runtime, typing a custom provider name + base URL in the
# MajiBot settings panel). "gemini" is special-cased — it uses Google's SDK,
# not the OpenAI-compatible chat-completions API — so it is intentionally
# absent from this map.
KNOWN_BASE_URLS: Dict[str, str] = {
    "grok": "https://api.x.ai/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4/",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "mistral": "https://api.mistral.ai/v1",
    "together": "https://api.together.xyz/v1",
}

# Alternative env/secret names accepted for a provider's API key, in addition
# to the canonical "<PROVIDER>_API_KEY".
_KEY_ALIASES: Dict[str, list] = {
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "grok": ["GROK_API_KEY", "XAI_API_KEY"],
    "glm": ["GLM_API_KEY", "ZHIPU_API_KEY"],
}


def resolve_base_url(provider: str, explicit: Optional[str] = None) -> Optional[str]:
    """Resolve the base URL for an OpenAI-compatible provider.

    Order: explicit value -> session/secret override -> built-in default.
    Returns None for gemini (handled by its own SDK).
    """
    provider = (provider or "").lower()
    if provider == "gemini":
        return None
    if explicit:
        return explicit.strip()
    ss = None
    try:
        ss = st.session_state.get(f"ai_base_url_{provider}")
    except Exception:
        ss = None
    secret = _get_secret(f"{provider.upper()}_BASE_URL")
    return (ss or secret or KNOWN_BASE_URLS.get(provider) or "").strip() or None


def resolve_api_key(provider: str) -> Optional[str]:
    """Resolve an API key for any provider from session, secrets, or env.

    Checks, in order: the in-session key entered via the settings panel,
    then the canonical "<PROVIDER>_API_KEY", then any known aliases.
    """
    provider = (provider or "").lower()
    try:
        ss_key = st.session_state.get(f"ai_api_key_{provider}")
    except Exception:
        ss_key = None
    if ss_key:
        return str(ss_key)
    names = _KEY_ALIASES.get(provider, [f"{provider.upper()}_API_KEY"])
    for name in names:
        val = _get_secret(name)
        if val:
            return str(val)
    return None


def active_provider() -> str:
    """The provider MajiBot/ChatLLM will use (session → secrets → 'gemini')."""
    try:
        ss_provider = st.session_state.get("ai_provider")
    except Exception:
        ss_provider = None
    return (ss_provider or _get_secret("LLM_PROVIDER", "gemini") or "gemini").lower()


def is_llm_configured() -> bool:
    """True when an API key is available for the active provider — i.e. AI
    features can run rather than falling back to a template."""
    try:
        return bool(resolve_api_key(active_provider()))
    except Exception:
        return False


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
    # Try st.secrets first (Streamlit Cloud or local .streamlit/secrets.toml)
    try:
        # Check top-level first
        if hasattr(st.secrets, name):
            val = getattr(st.secrets, name)
            if val not in (None, ""):
                return str(val)
        # Check under [llm] section
        if hasattr(st.secrets, "llm"):
            llm_secrets = st.secrets["llm"]
            if hasattr(llm_secrets, name):
                val = getattr(llm_secrets, name)
                if val not in (None, ""):
                    return str(val)
            elif isinstance(llm_secrets, dict) and name in llm_secrets:
                val = llm_secrets.get(name)
                if val not in (None, ""):
                    return str(val)
    except Exception:
        pass

    # Fallback: Load from local secrets.toml file directly
    local = _load_local_secrets() or {}
    if name in local and local.get(name) not in (None, ""):
        return str(local.get(name))
    if "llm" in local and isinstance(local["llm"], dict):
        val = local["llm"].get(name)
        if val not in (None, ""):
            return str(val)

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
        # Session-state overrides from the sidebar AI Settings panel
        ss_provider = st.session_state.get("ai_provider")
        ss_model = st.session_state.get("ai_model")
        self.cfg = cfg or LLMConfig(
            provider=ss_provider or _get_secret("LLM_PROVIDER", "gemini") or "gemini",
            model=ss_model or _get_secret("MODEL_ID", "gemini-1.5-flash") or "gemini-1.5-flash",
            temperature=float(_get_secret("TEMPERATURE", "0.2") or 0.2),
            max_tokens=int(_get_secret("MAX_TOKENS", "2048") or 2048),
        )

        self.provider = (self.cfg.provider or "gemini").lower()
        # Any provider name is accepted: "gemini" uses the Google SDK, anything
        # else is treated as OpenAI-compatible and dispatched through a base URL
        # (built-in or user-supplied). This is what makes new providers pluggable
        # without code changes.
        self.base_url = resolve_base_url(self.provider, self.cfg.base_url)
        if self.provider != "gemini" and not self.base_url:
            raise LLMNotConfiguredError(
                f"No base URL configured for provider '{self.provider}'. "
                f"Add one in MajiBot settings or set {self.provider.upper()}_BASE_URL."
            )

        # Lazy init for providers
        self._gemini_model = None
        self._openai_client = None

    # ---------------- Gemini helpers ----------------
    def _ensure_gemini(self):
        if self._gemini_model is not None:
            return self._gemini_model

        api_key = resolve_api_key("gemini")
        if not api_key:
            raise LLMNotConfiguredError(
                "Missing GEMINI_API_KEY or GOOGLE_API_KEY in st.secrets or environment."
            )
        
        # Sanitize key (remove whitespace and quotes)
        api_key = str(api_key).strip().strip('"').strip("'")
        
        # Check for placeholder values
        if "your_api_key_here" in api_key or "your_key_here" in api_key:
            raise LLMNotConfiguredError(
                "API key is still set to placeholder 'your_api_key_here'. Please configure a valid API key."
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

    def _ensure_openai(self):
        """Build (and cache) an OpenAI-compatible client for any non-Gemini
        provider, pointed at the resolved base URL (Grok, GLM, OpenAI,
        DeepSeek, OpenRouter, or any custom provider the user configures)."""
        if self._openai_client is not None:
            return self._openai_client

        api_key = resolve_api_key(self.provider)
        if not api_key:
            raise LLMNotConfiguredError(
                f"Missing API key for '{self.provider}'. Add it in MajiBot "
                f"settings or set {self.provider.upper()}_API_KEY."
            )

        api_key = str(api_key).strip().strip('"').strip("'")
        try:
            import openai
            self._openai_client = openai.OpenAI(api_key=api_key, base_url=self.base_url)
        except ImportError:
            raise LLMNotConfiguredError(
                "OpenAI SDK not installed. Add 'openai' to requirements.txt."
            )
        except Exception as e:
            raise LLMNotConfiguredError(
                f"Failed to initialize '{self.provider}' client: {e}"
            )

        return self._openai_client

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
                print(e)
                raise LLMNotConfiguredError(str(e))
        
        # Any non-Gemini provider goes through the OpenAI-compatible path.
        client = self._ensure_openai()
        try:
            response = client.chat.completions.create(
                model=model or self.cfg.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.cfg.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.cfg.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise LLMNotConfiguredError(str(e))

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
        
        # Any non-Gemini provider goes through the OpenAI-compatible path.
        client = self._ensure_openai()
        try:
            stream = client.chat.completions.create(
                model=model or self.cfg.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.cfg.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.cfg.max_tokens,
                stream=True
            )

            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            yield f"I encountered an error: {str(e)[:100]}. Please try again."
        return

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

    # ----------------------------------------------------------------
    # Text-to-SQL
    # ----------------------------------------------------------------

    def generate_sql(self, user_question: str) -> Optional[str]:
        """
        Generate a DuckDB SQL query from a natural language question.

        Returns the SQL string or None if generation fails.
        Safety: only SELECT statements are allowed.
        """
        try:
            from data.database import get_table_schemas
            from data.rag import retrieve_relevant_indicators
        except ImportError:
            return None

        table_ddl = get_table_schemas()
        indicator_context = retrieve_relevant_indicators(user_question, top_k=3)

        system_prompt = f"""You are a SQL query generator for a water utility analytics database (DuckDB).
Given a natural language question, produce a single SELECT query that answers it.

DATABASE SCHEMA:
{table_ddl}

DERIVED VIEWS AVAILABLE:
- v_billing_monthly(month, country, zone, customers, total_consumption_m3, total_billed, total_paid, collection_efficiency)
- v_production_monthly(month, country, source, total_production_m3, avg_service_hours, days_recorded)
- v_nrw_monthly(month, country, total_production_m3, total_consumption_m3, nrw_pct, avg_service_hours)
- v_service_quality(country, city, zone, month, year, date, w_supplied, total_consumption, metered, water_quality_rate, complaint_resolution_rate, nrw_rate, sewer_coverage_rate, ...)
- v_financial_monthly(date, country, city, sewer_revenue, opex, cost_recovery_pct, ...)

INDICATOR DEFINITIONS:
{indicator_context}

RULES:
1. Output ONLY the SQL query, no explanations
2. Only SELECT statements — never INSERT, UPDATE, DELETE, DROP, ALTER
3. Always add LIMIT 100 unless the user asks for all rows
4. Use the derived views (v_*) when they match the question
5. Country names are in title case (e.g., 'Cameroon', 'Uganda')
6. For percentage metrics, values are already 0-100 (not 0-1)
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ]

        try:
            raw = self.chat_once(messages, inject_context=False, max_tokens=512)
        except Exception:
            return None

        # Extract SQL from potential markdown code blocks
        sql = raw.strip()
        if "```" in sql:
            parts = sql.split("```")
            for part in parts:
                cleaned = part.strip()
                if cleaned.lower().startswith("sql"):
                    cleaned = cleaned[3:].strip()
                if cleaned.upper().startswith("SELECT"):
                    sql = cleaned
                    break

        # Safety validation
        sql_upper = sql.upper().strip()
        if not sql_upper.startswith("SELECT"):
            return None
        forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC"}
        tokens = set(sql_upper.split())
        if tokens & forbidden:
            return None

        return sql
