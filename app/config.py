"""Central settings — everything optional, demo mode works with zero keys."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    projects_dir: Path = Path(os.getenv("PROJECTS_DIR", str(ROOT / "projects")))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    pexels_api_key: str = os.getenv("PEXELS_API_KEY", "")
    youtube_client_id: str = os.getenv("YOUTUBE_CLIENT_ID", "")
    youtube_client_secret: str = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    drive_folder_id: str = os.getenv("DRIVE_FOLDER_ID", "")
    credentials_file: Path = Path(os.getenv("YOUTUBE_CREDENTIALS", str(ROOT / "credentials.json")))
    token_file: Path = Path(os.getenv("YOUTUBE_TOKEN", str(ROOT / "token.json")))

    # Video presets
    formats: dict = field(default_factory=lambda: {
        "16:9": {"w": 1280, "h": 720},
        "9:16": {"w": 720, "h": 1280},
    })
    durations: dict = field(default_factory=lambda: {
        "60s": 60, "2min": 120, "5min": 300, "10min": 600,
    })
    # Edge-TTS voices (free, no key). Piper voices can be added via PIPER_VOICES env.
    voices: dict = field(default_factory=lambda: {
        "en-female": "en-US-AriaNeural",
        "en-male": "en-US-GuyNeural",
        "en-gb": "en-GB-SoniaNeural",
        "es": "es-ES-ElviraNeural",
        "fr": "fr-FR-DeniseNeural",
        "de": "de-DE-KatjaNeural",
        "hi": "hi-IN-SwaraNeural",
        "ar": "ar-SA-ZariyahNeural",
    })
    languages: dict = field(default_factory=lambda: {
        "en": "English", "es": "Spanish", "fr": "French", "de": "German",
        "hi": "Hindi", "ar": "Arabic",
    })


settings = Settings()
settings.projects_dir.mkdir(parents=True, exist_ok=True)
