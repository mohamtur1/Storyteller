"""Storyteller — FastAPI app. Mobile-first, single-page UI + REST API."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pipeline, store, youtube as yt_mod
from .config import settings

app = FastAPI(title="Storyteller", version="1.0.0")
STATIC = Path(__file__).resolve().parent.parent / "static"


class CreateProject(BaseModel):
    topic: str
    description: str = ""
    duration_sec: int = 60
    format: str = "16:9"
    voice: str = "en-female"
    language: str = "en"


class PublishRequest(BaseModel):
    privacy: str = "unlisted"


@app.get("/api/health")
def health():
    return {"ok": True, "version": "1.0.0", "youtube_configured": yt_mod.is_configured(),
            "formats": list(settings.formats.keys()),
            "durations": settings.durations,
            "voices": list(settings.voices.keys()),
            "languages": settings.languages}


@app.post("/api/projects")
def create(req: CreateProject):
    if not req.topic.strip():
        raise HTTPException(400, "Topic is required")
    p = store.create_project(req.topic.strip(), req.description, req.duration_sec,
                             req.format, req.voice, req.language)
    pipeline.start_async(p.id)
    return p.to_dict()


@app.get("/api/projects")
def list_all():
    return [p.to_dict() for p in store.list_projects()]


@app.get("/api/projects/{pid}")
def get(pid: str):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p.to_dict()


@app.post("/api/projects/{pid}/retry")
def retry(pid: str):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "Project not found")
    # Reset failed stage onwards: drop last done stage so it re-runs
    store.update(pid, status="pending", error="")
    pipeline.start_async(pid)
    return store.get_project(pid).to_dict()


@app.post("/api/projects/{pid}/publish")
def publish(pid: str, req: PublishRequest):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "Project not found")
    if p.status != "awaiting_approval":
        raise HTTPException(400, "Video must be finished and approved before publishing")
    video = Path(p.data.get("video", ""))
    thumb = Path(p.data.get("thumbnail", ""))
    meta = p.data.get("metadata", {})
    if not video.exists():
        raise HTTPException(400, "Video file missing")
    meta = {**meta, "privacy": req.privacy}
    if yt_mod.is_configured():
        try:
            res = yt_mod.upload_video(video, thumb, meta)
            store.update(pid, status="done", youtube_url=res["url"])
            return {"published": True, **res}
        except Exception as e:
            raise HTTPException(500, f"YouTube upload failed: {e}. Use manual upload instead.")
    # Manual package fallback
    res = yt_mod.manual_package(video, thumb, meta, p.dir / "Metadata" / "manual_upload")
    return {"published": False, "manual": True, **res,
            "message": "YouTube API not configured — manual upload package ready."}


@app.get("/api/projects/{pid}/file")
def serve_file(pid: str, path: str):
    """Serve project files (video preview, thumbnail, srt, txt)."""
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "Project not found")
    target = (p.dir / path).resolve()
    if not str(target).startswith(str(p.dir.resolve())):
        raise HTTPException(403, "Forbidden")
    if not target.exists() or target.is_dir():
        raise HTTPException(404, "File not found")
    return FileResponse(target)


# --- Static frontend ---
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
