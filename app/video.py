"""Stage E — Video assembly with FFmpeg. Slideshow + narration + subtitles + intro/outro."""
from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path


def _ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        p = shutil.which("ffmpeg")
        if not p:
            raise RuntimeError("ffmpeg not found. Run: pip install imageio-ffmpeg")
        return p


def _probe_duration(path: Path, ff: str) -> float:
    """Get audio duration via ffprobe if available, else estimate from file size."""
    probe = shutil.which("ffprobe")
    if probe:
        try:
            r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                               capture_output=True, text=True, timeout=15)
            return max(2.0, float(r.stdout.strip()))
        except Exception:
            pass
    # Rough MP3 estimate: ~16KB/s at 128kbps
    try:
        return max(3.0, path.stat().st_size / 16000)
    except Exception:
        return 5.0


def build_srt(scenes: list[dict], audio_durations: list[float], dest: Path) -> Path:
    """Word-timed-ish subtitles: each scene's narration shown during its audio."""
    def ts(sec: float) -> str:
        h, rem = divmod(int(sec), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{int((sec - int(sec)) * 1000):03d}"

    t = 0.0
    lines = []
    for i, (scene, dur) in enumerate(zip(scenes, audio_durations)):
        text = " ".join(scene["narration"].split())
        # Wrap to ~42 chars for readability
        wrapped = "\n".join(textwrap.wrap(text, width=42)) or text
        lines.append(f"{i + 1}\n{ts(t)} --> {ts(t + dur)}\n{wrapped}\n")
        t += dur
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def assemble(images: list[dict], audios: list[dict], srt_path: Path | None,
             dest: Path, w: int = 1280, h: int = 720) -> Path:
    """Build MP4: each image shown for its narration duration, audio concatenated."""
    ff = _ffmpeg()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / "_build"
    tmp.mkdir(exist_ok=True)

    durations = [_probe_duration(Path(a["path"]), ff) for a in audios]

    # 1. Per-scene segments (image + audio, with fade in/out)
    segments = []
    for i, (img, aud, dur) in enumerate(zip(images, audios, durations)):
        seg = tmp / f"seg_{i:02d}.mp4"
        img_path = img["path"] if isinstance(img, dict) else str(img)
        aud_path = aud["path"] if isinstance(aud, dict) else str(aud)
        # Scale/pad to exact video size, Ken Burns-ish zoom via zoompan is heavy — use scale+fade
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
              f"format=yuv420p,fade=t=in:st=0:d=0.4,fade=t=out:st={max(0, dur - 0.4):.2f}:d=0.4")
        cmd = [ff, "-y", "-loop", "1", "-i", img_path, "-i", aud_path,
               "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
               "-c:a", "aac", "-b:a", "128k", "-shortest", "-t", f"{dur:.2f}", str(seg)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not seg.exists():
            # Fallback: solid-color segment (never fail the whole video)
            cmd2 = [ff, "-y", "-f", "lavfi", "-i", f"color=c=0x1a2a4a:s={w}x{h}:r=30:d={dur:.2f}",
                    "-i", aud_path, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(seg)]
            subprocess.run(cmd2, capture_output=True, timeout=300)
        segments.append(seg)

    # 2. Concat
    concat_list = tmp / "concat.txt"
    concat_list.write_text("".join(f"file '{s}'\n" for s in segments), encoding="utf-8")
    joined = tmp / "joined.mp4"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                    "-c", "copy", str(joined)], capture_output=True, timeout=300)

    # 3. Burn subtitles (if font available) + faststart for YouTube streaming
    if srt_path and srt_path.exists():
        srt_esc = str(srt_path).replace(":", "\\:").replace("'", "\\'")
        vf = f"subtitles='{srt_esc}':force_style='FontSize=20,PrimaryColour=&HFFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=40'"
        r = subprocess.run([ff, "-y", "-i", str(joined), "-vf", vf,
                            "-c:a", "copy", "-movflags", "+faststart", str(dest)],
                           capture_output=True, timeout=600)
        if r.returncode != 0:
            # Subtitle burn failed (missing font) — ship without burned subs; .srt still attached
            subprocess.run([ff, "-y", "-i", str(joined), "-c", "copy",
                            "-movflags", "+faststart", str(dest)], capture_output=True, timeout=300)
    else:
        subprocess.run([ff, "-y", "-i", str(joined), "-c", "copy",
                        "-movflags", "+faststart", str(dest)], capture_output=True, timeout=300)

    # Cleanup build dir
    for f in tmp.iterdir():
        try:
            f.unlink()
        except Exception:
            pass
    try:
        tmp.rmdir()
    except Exception:
        pass
    return dest
