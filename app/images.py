"""Stage C — Images. Openverse (no key) + Pexels (optional) + PIL gradient fallback."""
from __future__ import annotations

from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

UA = {"User-Agent": "Storyteller/1.0 (educational video tool)"}


def _download(url: str, dest: Path, timeout: int = 20) -> bool:
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        if r.status_code == 200 and len(r.content) > 5000:
            dest.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def openverse(query: str, count: int = 3) -> list[dict]:
    """Openverse API — CC images, no key required for basic use."""
    try:
        r = requests.get("https://api.openverse.org/v1/images/",
                         params={"q": query, "page_size": count, "license_type": "all"},
                         headers=UA, timeout=15)
        if r.status_code != 200:
            return []
        out = []
        for item in r.json().get("results", []):
            if item.get("url"):
                out.append({"url": item["url"], "title": item.get("title", query),
                            "source": item.get("foreign_landing_url") or item.get("url"),
                            "license": item.get("license", "CC")})
        return out
    except Exception:
        return []


def pexels(query: str, count: int = 3) -> list[dict]:
    import os
    key = os.getenv("PEXELS_API_KEY", "")
    if not key:
        return []
    try:
        r = requests.get("https://api.pexels.com/v1/search",
                         params={"query": query, "per_page": count, "orientation": "landscape"},
                         headers={"Authorization": key}, timeout=15)
        if r.status_code != 200:
            return []
        out = []
        for p in r.json().get("photos", []):
            src = p.get("src", {})
            out.append({"url": src.get("large2x") or src.get("large") or "",
                        "title": p.get("alt", query), "source": p.get("url", ""),
                        "license": "Pexels License (free)"})
        return [o for o in out if o["url"]]
    except Exception:
        return []


def gradient_slide(text: str, dest: Path, w: int = 1280, h: int = 720, hue: int = 0) -> Path:
    """Beautiful branded fallback slide — pipeline never fails for lack of photos."""
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    # Vertical gradient
    for y in range(h):
        t = y / h
        r = int(15 + 30 * t + (hue % 60))
        g = int(25 + 20 * t)
        b = int(60 + 80 * t)
        d.line([(0, y), (w, y)], fill=(r, g, b))
    # Accent bar
    d.rectangle([0, int(h * 0.78), w, int(h * 0.80)], fill=(255, 200, 60))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(h * 0.07))
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(h * 0.035))
    except Exception:
        font, small = ImageFont.load_default(), ImageFont.load_default()
    # Word-wrap title
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if d.textlength(trial, font=font) < w * 0.85:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    lines = lines[:3]
    y0 = int(h * 0.38) - len(lines) * int(h * 0.09) // 2
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=font)
        d.text(((w - tw) / 2, y0 + i * int(h * 0.09)), line, font=font, fill=(255, 255, 255))
    tag = "STORYTELLER"
    tw = d.textlength(tag, font=small)
    d.text(((w - tw) / 2, int(h * 0.84)), tag, font=small, fill=(200, 210, 230))
    img.save(dest, "JPEG", quality=88)
    return dest


def collect_images(scenes: list[dict], dest_dir: Path, w: int = 1280, h: int = 720) -> list[dict]:
    """Download one image per scene. Returns [{path, source, license, title}]."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    results = []
    credits = []
    for i, scene in enumerate(scenes):
        query = scene.get("visual_query", "education")
        dest = dest_dir / f"scene_{i + 1:02d}.jpg"
        candidates = pexels(query) + openverse(query)
        got = None
        for c in candidates:
            if _download(c["url"], dest):
                got = c
                break
        if got:
            # Normalize size (cover-crop to target)
            try:
                im = Image.open(dest).convert("RGB")
                im.thumbnail((w * 2, h * 2))
                im.save(dest, "JPEG", quality=88)
            except Exception:
                pass
            credits.append(f"Scene {i + 1}: {got['title']} — {got['source']} ({got['license']})")
        else:
            gradient_slide(scene.get("narration", query)[:80], dest, w, h, hue=i * 37)
            credits.append(f"Scene {i + 1}: generated gradient slide (no photo found for '{query}')")
        results.append({"path": str(dest), "source": got["source"] if got else "generated",
                        "license": got["license"] if got else "generated",
                        "title": got["title"] if got else query})
    (dest_dir / "credits.txt").write_text("\n".join(credits), encoding="utf-8")
    return results
