"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def parse_key_map(raw: str) -> dict[str, str]:
    """'p1-rajat:key1,p1-teamB:key2' -> {'key1': 'p1-rajat', 'key2': 'p1-teamB'}."""
    out: dict[str, str] = {}
    for part in (raw or "").split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        source, key = part.split(":", 1)
        source, key = source.strip(), key.strip()
        if source and key:
            out[key] = source
    return out


@dataclass
class Settings:
    database_url: str = ""
    admin_api_key: str = ""                 # P2_API_KEY: admin / master key
    source_keys: dict = field(default_factory=dict)   # P2_API_KEYS: key -> source_system
    verify_token: str = ""
    wa_token: str = ""
    wa_phone_number_id: str = ""
    wa_app_secret: str = ""
    wa_display_number: str = ""             # the WhatsApp number users chat with (for wa.me links)
    graph_version: str = "v21.0"
    graph_base: str = "https://graph.facebook.com"
    invite_template: str = "hello_world"
    invite_template_lang: str = "en_US"
    allowed_origins: list = field(default_factory=list)
    companion_public: bool = True
    public_base_url: str = ""
    max_results: int = 5
    log_level: str = "INFO"

    @property
    def whatsapp_configured(self) -> bool:
        return bool(self.wa_token and self.wa_phone_number_id)


def load_settings() -> Settings:
    db = _env("DATABASE_URL", "sqlite:///./p2_local.db")
    origins = [o.strip() for o in _env("ALLOWED_ORIGINS").split(",") if o.strip()]
    base = _env("PUBLIC_BASE_URL")
    if not base and _env("RENDER_EXTERNAL_URL"):
        base = _env("RENDER_EXTERNAL_URL")          # set automatically by Render
    return Settings(
        database_url=db,
        admin_api_key=_env("P2_API_KEY"),
        source_keys=parse_key_map(_env("P2_API_KEYS")),
        verify_token=_env("WHATSAPP_VERIFY_TOKEN"),
        wa_token=_env("WHATSAPP_TOKEN"),
        wa_phone_number_id=_env("WHATSAPP_PHONE_NUMBER_ID"),
        wa_app_secret=_env("WHATSAPP_APP_SECRET"),
        wa_display_number="".join(ch for ch in _env("WHATSAPP_DISPLAY_NUMBER") if ch.isdigit()),
        graph_version=_env("WHATSAPP_GRAPH_VERSION", "v21.0"),
        graph_base=_env("WHATSAPP_GRAPH_BASE", "https://graph.facebook.com"),
        invite_template=_env("WHATSAPP_INVITE_TEMPLATE", "hello_world"),
        invite_template_lang=_env("WHATSAPP_INVITE_TEMPLATE_LANG", "en_US"),
        allowed_origins=origins,
        companion_public=_env("COMPANION_PUBLIC", "true").lower() in {"1", "true", "yes"},
        public_base_url=base.rstrip("/"),
        max_results=int(_env("P2_MAX_RESULTS", "5") or 5),
        log_level=_env("LOG_LEVEL", "INFO"),
    )


settings = load_settings()


def reload_settings() -> Settings:
    """Used by tests after changing environment variables."""
    global settings
    new = load_settings()
    settings.__dict__.update(new.__dict__)
    return settings
