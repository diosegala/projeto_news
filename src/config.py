# src/config.py — centralized config (Streamlit secrets only, Service Account only)
from __future__ import annotations
import json
from typing import Any, Optional, Dict
import streamlit as st


def _from_secrets(key: str, default=None):
    try:
        val = st.secrets.get(key)
        return val if val not in (None, "") else default
    except Exception:
        return default

class Config:
    DEBUG = bool(_from_secrets("DEBUG", False))

    # API Keys
    OPENAI_API_KEY = _from_secrets("OPENAI_API_KEY")
    GOOGLE_API_KEY = _from_secrets("GOOGLE_API_KEY")

    # OAuth (LEGACY — mantidas por compat, mas não usadas no deploy)
    OAUTH_CLIENT_SECRETS = _from_secrets("GOOGLE_OAUTH_CLIENT_SECRETS")
    TOKEN_PATH = _from_secrets("GOOGLE_OAUTH_TOKEN_PATH", "token.json")

    # Google Drive/Docs
    GDRIVE_FOLDER_ID = _from_secrets("GDRIVE_FOLDER_ID")
    GDOC_TITLE = _from_secrets("GDOC_TITLE", "Imobi Report – Resumos")

    #Headers HTTP
    HEADERS = _from_secrets("HEADERS")

    # Modelos
    MODEL_CHOICES = [
        "Gemini: gemini-2.5-pro",
        "Gemini: gemini-2.5-flash",
        "Gemini: gemini-2.5-flash-lite",
        "OpenAI: gpt-4o-mini",
        "OpenAI: gpt-5",
    ]

    MAX_LINKS_PER_BATCH = int(_from_secrets("MAX_LINKS_PER_BATCH", 50))
    BATCH_SIZE = int(_from_secrets("BATCH_SIZE", 12))
    REQUEST_TIMEOUT = int(_from_secrets("REQUEST_TIMEOUT", 30))

    CONTEXT_LIMITS = {
        "gemini-2.5-pro": {"lead_clip": 25000, "note_clip": 3000, "max_notes": 45},
        "gemini-2.5-flash": {"lead_clip": 20000, "note_clip": 2500, "max_notes": 45},
        "gemini-2.5-flash-lite": {"lead_clip": 20000, "note_clip": 2200, "max_notes": 45},
        "gpt-4o-mini": {"lead_clip": 12000, "note_clip": 1800, "max_notes": 28},
        "gpt-5": {"lead_clip": 10000, "note_clip": 1500, "max_notes": 25},
    }

    # Logins: se quiser, crie um bloco [LOGINS] no secrets.toml
    LOGINS = _from_secrets("LOGINS")

    # Paths
    DB_PATH = "data/db.json"
    USERS_DB_PATH = "data/users.json"
    STYLE_GUIDE_PATH = "data/style_guide.md"

    
    @staticmethod
    def sa_configured() -> bool:
        info = Config.get_service_account_info()
        return bool(info and info.get("client_email") and info.get("private_key"))


    @staticmethod
    def get_service_account_info() -> dict:
        raw = _from_secrets("GOOGLE_SERVICE_ACCOUNT")
        if not raw:
            return {}
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
        if isinstance(raw, dict):
            return raw
        try:
            return dict(raw)
        except Exception:
            return {}

    @staticmethod
    def get_context_limits(model_name: str) -> dict:
        clean = model_name.split(":")[-1].strip() if ":" in model_name else model_name
        return Config.CONTEXT_LIMITS.get(clean, Config.CONTEXT_LIMITS["gpt-4o-mini"])