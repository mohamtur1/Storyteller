"""Pipeline orchestrator — runs stages in order, skips completed ones (resume-safe)."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from . import drive as drive_mod
from . import images as images_mod
from . import metadata as metadata_mod
from . import research as research_mod
from . import script as script_mod
from . import store
from . import thumbnail as thumbnail_mod
from . import tts as tts_mod
from . import video as video_mod
from .config import settings

STAGE_PROGRESS = {
    "research": 10, "script": 25, "images": 45, "narration": 60,
    "subtitles": 70, "video": 85, "thumbnail": 92, "metadata": 96, "done": 100,
}


def _set(pid: str, stage: str, status: str = "running", error: str = "") -> None:
    store.update(pid, stage=stage, status=status, progress=STAGE_PROGRESS.get(stage, 0), error=error)


def _done(pid: str, stage: str, key: str | None = None, value=None) -> None:
    """Mark stage complete AND persist its output data (resume-safe)."""
    p = store.get_project(pid)
    if not p:
        return
    done = list(p.stages_done)
    if stage not in done:
        done.append(stage)
    data = dict(p.data)
    if key:
        data[key] = value
    store.update(pid, stages_done=done, data=data)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_pipeline(pid: str) -> None:
    """Full pipeline. Safe to re-run: completed stages are skipped."""
    p = store.get_project(pid)
    if not p:
        return
    d = p.dir
    fmt = settings.formats.get(p.format, {"w": 1280, "h": 720})
    W, H = fmt["w"], fmt["h"]
    try:
        # --- Stage A: Research ---
        if "research" not in p.stages_done:
            _set(pid, "research")
            res = research_mod.research(p.topic)
            _save_json(d / "Research" / "research.json", res)
            (d / "Research" / "summary.txt").write_text(
                f"{res['title']}\n\n{res['summary']}\n\nFacts:\n" +
                "\n".join(f"- {f}" for f in res["facts"]) +
                "\n\nSources:\n" + "\n".join(res["sources"]), encoding="utf-8")
            _done(pid, "research", "research", res)
            p = store.get_project(pid)

        # --- Stage B: Script ---
        if "script" not in p.stages_done:
            _set(pid, "script")
            scr = script_mod.build_script(p.topic, p.data.get("research", {}),
                                          p.duration_sec, p.language, p.description)
            _save_json(d / "Script" / "script.json", scr)
            (d / "Script" / "script.txt").write_text(scr["full_text"], encoding="utf-8")
            _done(pid, "script", "script", scr)
            p = store.get_project(pid)

        # --- Stage C: Images ---
        if "images" not in p.stages_done:
            _set(pid, "images")
            imgs = images_mod.collect_images(p.data["script"]["scenes"], d / "Images", W, H)
            _save_json(d / "Images" / "images.json", imgs)
            _done(pid, "images", "images", imgs)
            p = store.get_project(pid)

        # --- Stage D: Narration ---
        if "narration" not in p.stages_done:
            _set(pid, "narration")
            auds = tts_mod.synthesize_all(p.data["script"]["scenes"], d / "Audio", p.voice, p.language)
            _save_json(d / "Audio" / "audio.json", auds)
            _done(pid, "narration", "audio", auds)
            p = store.get_project(pid)

        # --- Stage E1: Subtitles ---
        if "subtitles" not in p.stages_done:
            _set(pid, "subtitles")
            from .video import _probe_duration, _ffmpeg, build_srt
            ff = _ffmpeg()
            durs = [_probe_duration(Path(a["path"]), ff) for a in p.data["audio"]]
            srt = build_srt(p.data["script"]["scenes"], durs, d / "Subtitles" / "captions.srt")
            _done(pid, "subtitles", "srt", str(srt))
            p = store.get_project(pid)

        # --- Stage E2: Video ---
        if "video" not in p.stages_done:
            _set(pid, "video")
            out = d / "FinalVideo" / "video.mp4"
            video_mod.assemble(p.data["images"], p.data["audio"],
                               Path(p.data.get("srt", "")) if p.data.get("srt") else None,
                               out, W, H)
            _done(pid, "video", "video", str(out))
            p = store.get_project(pid)

        # --- Stage F: Thumbnail ---
        if "thumbnail" not in p.stages_done:
            _set(pid, "thumbnail")
            bg = p.data["images"][0]["path"] if p.data.get("images") else None
            thumb = thumbnail_mod.make_thumbnail(p.topic, bg, d / "Thumbnail" / "thumbnail.jpg")
            _done(pid, "thumbnail", "thumbnail", str(thumb))
            p = store.get_project(pid)

        # --- Stage G: Metadata ---
        if "metadata" not in p.stages_done:
            _set(pid, "metadata")
            meta = metadata_mod.build_metadata(p.topic, p.data.get("research", {}),
                                               p.duration_sec, p.format, p.language)
            _save_json(d / "Metadata" / "metadata.json", meta)
            (d / "Metadata" / "description.txt").write_text(meta["description"], encoding="utf-8")
            _done(pid, "metadata", "metadata", meta)
            p = store.get_project(pid)

        # --- Archive to Drive (best effort) ---
        try:
            arch = drive_mod.archive(d)
            p.data["archive"] = arch
            if arch.get("drive_url"):
                store.update(pid, drive_url=arch["drive_url"])
        except Exception:
            pass

        store.update(pid, stage="done", status="awaiting_approval", progress=100,
                     data=p.data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        store.update(pid, status="failed", error=str(e)[:500])


def start_async(pid: str) -> None:
    t = threading.Thread(target=run_pipeline, args=(pid,), daemon=True)
    t.start()
