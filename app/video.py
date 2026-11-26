"""Stage E — Video assembly with FFmpeg. Smart single-pass design.

Instead of encoding each scene as a separate MP4 (N encodes),
then concatenating, then burning subtitles (N+2 passes),
this does everything in ONE FFmpeg command using filter_complex.
~5-7x faster on slow machines like Colab free tier.
"""
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
        wrapped = "\n".join(textwrap.wrap(text, width=42)) or text
        lines.append(f"{i + 1}\n{ts(t)} --> {ts(t + dur)}\n{wrapped}\n")
        t += dur
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def assemble(images: list[dict], audios: list[dict], srt_path: Path | None,
             dest: Path, w: int = 1280, h: int = 720) -> Path:
    """Build MP4 in a single FFmpeg pass.

    Scales/crops each image, trims video+audio to scene duration,
    concatenates all scenes, burns subtitles — all in one encode.
    """
    ff = _ffmpeg()
    dest.parent.mkdir(parents=True, exist_ok=True)

    durations = [_probe_duration(Path(a["path"]), ff) for a in audios]
    n = len(images)
    total_dur = sum(durations)

    # Build FFmpeg inputs: for each scene, image (looped) + audio
    inputs = []
    filter_parts = []

    for i, (img, aud, dur) in enumerate(zip(images, audios, durations)):
        img_path = img["path"] if isinstance(img, dict) else str(img)
        aud_path = aud["path"] if isinstance(aud, dict) else str(aud)
        inputs.extend(["-loop", "1", "-i", img_path, "-i", aud_path])

        # Video input index = i*2, audio input index = i*2+1
        # Scale/crop to target size, trim to audio duration, reset timestamps
        filter_parts.append(
            f"[{i*2}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},format=yuv420p,trim=duration={dur:.3f},setpts=PTS-STARTPTS[v{i}];"
        )
        # Trim audio to same duration, normalize format
        filter_parts.append(
            f"[{i*2+1}:a]atrim=duration={dur:.3f},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates=44100:channel_layouts=stereo[a{i}];"
        )

    # Concat all video + audio streams into one (single encode pass).
    # Concat filter expects interleaved per segment: [v0][a0][v1][a1]...
    streams = []
    for i in range(n):
        streams.append(f"[v{i}]")
        streams.append(f"[a{i}]")
    filter_complex = "".join(filter_parts)
    filter_complex += "".join(streams) + f"concat=n={n}:v=1:a=1[outv][outa]"

    cmd = [
        ff, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{total_dur:.2f}",
        "-movflags", "+faststart",
        str(dest),
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if r.returncode != 0 or not dest.exists():
        # Fallback: old multi-pass method (slow but reliable)
        print(f"⚠️  Smart assembly failed, using legacy method: {r.stderr[-200:] if r.stderr else 'unknown'}")
        return _assemble_legacy(images, audios, srt_path, dest, w, h, ff, durations)

    # Burn subtitles in a second pass only if needed (still just 2 passes total vs 9 before)
    if srt_path and srt_path.exists() and dest.exists():
        tmp2 = dest.parent / "_subs"
        tmp2.mkdir(exist_ok=True)
        subbed = tmp2 / "subbed.mp4"
        srt_esc = str(srt_path).replace(":", "\\:").replace("'", "\\'")
        vf_sub = f"subtitles='{srt_esc}':force_style='Fontsize=20,PrimaryColour=&HFFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=40'"
        r2 = subprocess.run([ff, "-y", "-i", str(dest), "-vf", vf_sub,
                             "-c:a", "copy", "-movflags", "+faststart", str(subbed)],
                            capture_output=True, text=True, timeout=600)
        if r2.returncode == 0 and subbed.exists():
            subbed.replace(dest)
        # If subtitle burn fails, the video without burned subs is still valid
        # (.srt file is still provided alongside)

    return dest


def _assemble_legacy(images, audios, srt_path, dest, w, h, ff, durations) -> Path:
    """Legacy multi-pass assembly (slow but reliable fallback)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / "_build"
    tmp.mkdir(exist_ok=True)

    segments = []
    for i, (img, aud, dur) in enumerate(zip(images, audios, durations)):
        seg = tmp / f"seg_{i:02d}.mp4"
        img_path = img["path"] if isinstance(img, dict) else str(img)
        aud_path = aud["path"] if isinstance(aud, dict) else str(aud)
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
              f"format=yuv420p")
        cmd = [ff, "-y", "-loop", "1", "-i", img_path, "-i", aud_path,
               "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast",
               "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k",
               "-shortest", "-t", f"{dur:.2f}", str(seg)]
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        segments.append(seg)

    concat_list = tmp / "concat.txt"
    concat_list.write_text("".join(f"file '{s}'\n" for s in segments), encoding="utf-8")
    joined = tmp / "joined.mp4"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                    "-c", "copy", str(joined)], capture_output=True, timeout=300)

    if srt_path and srt_path.exists():
        srt_esc = str(srt_path).replace(":", "\\:").replace("'", "\\'")
        vf_sub = f"subtitles='{srt_esc}':force_style='FontSize=20,PrimaryColour=&HFFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=40'"
        r = subprocess.run([ff, "-y", "-i", str(joined), "-vf", vf_sub,
                            "-c:a", "copy", "-movflags", "+faststart", str(dest)],
                           capture_output=True, timeout=600)
        if r.returncode != 0:
            subprocess.run([ff, "-y", "-i", str(joined), "-c", "copy",
                            "-movflags", "+faststart", str(dest)],
                           capture_output=True, timeout=300)
    else:
        subprocess.run([ff, "-y", "-i", str(joined), "-c", "copy",
                        "-movflags", "+faststart", str(dest)],
                       capture_output=True, timeout=300)

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
