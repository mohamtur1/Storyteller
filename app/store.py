"""Project state store — JSON per project, resume-safe."""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import settings

STAGES = [
    "research", "script", "images", "narration",
    "subtitles", "video", "thumbnail", "metadata", "done",
]

_lock = threading.Lock()


@dataclass
class Project:
    id: str
    topic: str
    description: str = ""
    duration_sec: int = 60
    format: str = "16:9"
    voice: str = "en-female"
    language: str = "en"
    status: str = "pending"          # pending | running | awaiting_approval | done | failed
    stage: str = "research"
    progress: int = 0                # 0-100
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    stages_done: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    youtube_url: str = ""
    drive_url: str = ""

    @property
    def dir(self) -> Path:
        return settings.projects_dir / self.id

    def save(self) -> None:
        self.updated_at = time.time()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "project.json").write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "topic": self.topic, "description": self.description,
            "duration_sec": self.duration_sec, "format": self.format,
            "voice": self.voice, "language": self.language,
            "status": self.status, "stage": self.stage, "progress": self.progress,
            "error": self.error, "created_at": self.created_at,
            "updated_at": self.updated_at, "stages_done": self.stages_done,
            "data": self.data, "youtube_url": self.youtube_url, "drive_url": self.drive_url,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(
            id=d["id"], topic=d["topic"], description=d.get("description", ""),
            duration_sec=d.get("duration_sec", 60), format=d.get("format", "16:9"),
            voice=d.get("voice", "en-female"), language=d.get("language", "en"),
            status=d.get("status", "pending"), stage=d.get("stage", "research"),
            progress=d.get("progress", 0), error=d.get("error", ""),
            created_at=d.get("created_at", time.time()), updated_at=d.get("updated_at", time.time()),
            stages_done=d.get("stages_done", []), data=d.get("data", {}),
            youtube_url=d.get("youtube_url", ""), drive_url=d.get("drive_url", ""),
        )


def create_project(topic: str, description: str = "", duration_sec: int = 60,
                   fmt: str = "16:9", voice: str = "en-female", language: str = "en") -> Project:
    pid = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    p = Project(id=pid, topic=topic, description=description, duration_sec=duration_sec,
                format=fmt, voice=voice, language=language)
    p.dir.mkdir(parents=True, exist_ok=True)
    for sub in ["Research", "Script", "Images", "Audio", "Subtitles", "Thumbnail", "FinalVideo", "Metadata"]:
        (p.dir / sub).mkdir(parents=True, exist_ok=True)
    p.save()
    return p


def get_project(pid: str) -> Project | None:
    f = settings.projects_dir / pid / "project.json"
    if not f.exists():
        return None
    return Project.from_dict(json.loads(f.read_text(encoding="utf-8")))


def list_projects() -> list[Project]:
    out = []
    if not settings.projects_dir.exists():
        return out
    for d in sorted(settings.projects_dir.iterdir(), reverse=True):
        f = d / "project.json"
        if f.exists():
            try:
                out.append(Project.from_dict(json.loads(f.read_text(encoding="utf-8"))))
            except Exception:
                continue
    return out


def update(pid: str, **kwargs) -> Project | None:
    with _lock:
        p = get_project(pid)
        if not p:
            return None
        for k, v in kwargs.items():
            setattr(p, k, v)
        p.save()
        return p
