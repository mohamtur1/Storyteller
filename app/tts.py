"""Stage D — Narration. Edge-TTS (free) → gTTS → Piper (if installed) → silent audio."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from .config import settings

# Piper voices: place .onnx files in voices/ and set PIPER_VOICES="path1,path2"
import os
PIPER_VOICES = [v.strip() for v in os.getenv("PIPER_VOICES", "").split(",") if v.strip()]


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _silent_audio(dest: Path, seconds: float) -> Path:
    """Last-resort: timed silence so the video still renders (subtitles carry the words)."""
    ff = _ffmpeg()
    if ff:
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-t", str(max(1, seconds)), "-c:a", "libmp3lame", str(dest)],
                       capture_output=True, timeout=60)
    else:
        dest.write_bytes(b"")  # empty placeholder; video stage handles it
    return dest


async def _edge(text: str, voice: str, dest: Path) -> bool:
    try:
        import edge_tts
        await edge_tts.Communicate(text, voice).save(str(dest))
        return dest.exists() and dest.stat().st_size > 1000
    except Exception:
        return False


def _gtts(text: str, lang: str, dest: Path) -> bool:
    try:
        from gtts import gTTS
        gTTS(text=text, lang=lang).save(str(dest))
        return dest.exists() and dest.stat().st_size > 500
    except Exception:
        return False


def _piper(text: str, model: str, dest: Path) -> bool:
    try:
        proc = subprocess.run(["piper", "--model", model, "--output_file", str(dest)],
                              input=text.encode(), capture_output=True, timeout=120)
        return proc.returncode == 0 and dest.exists() and dest.stat().st_size > 1000
    except Exception:
        return False


def synthesize_scene(text: str, dest: Path, voice_key: str = "en-female", language: str = "en") -> dict:
    """Synthesize one scene. Returns {path, engine, duration_sec_estimate}."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    engine = "silent"
    # 1. Piper (offline, best quality if installed)
    for model in PIPER_VOICES:
        if _piper(text, model, dest):
            engine = "piper"
            break
    # 2. Edge-TTS (free, natural, no key)
    if engine == "silent":
        voice = settings.voices.get(voice_key, "en-US-AriaNeural")
        if asyncio.run(_edge(text, voice, dest)):
            engine = "edge-tts"
    # 3. gTTS
    if engine == "silent" and _gtts(text, language, dest):
        engine = "gtts"
    # 4. Silence fallback (never crash the pipeline)
    if engine == "silent":
        est = max(3, len(text.split()) / 2.5)
        _silent_audio(dest, est)
    # Estimate duration from file size if possible, else word count
    est = max(3, len(text.split()) / 2.5)
    return {"path": str(dest), "engine": engine, "duration_sec": est, "text": text}


def synthesize_all(scenes: list[dict], dest_dir: Path, voice_key: str, language: str) -> list[dict]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, s in enumerate(scenes):
        out.append(synthesize_scene(s["narration"], dest_dir / f"scene_{i + 1:02d}.mp3", voice_key, language))
    return out
