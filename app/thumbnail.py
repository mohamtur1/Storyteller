"""Stage F — 1280x720 YouTube thumbnail. Big text, high contrast, face-friendly."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720


def _font(size: int, bold: bool = True):
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_thumbnail(topic: str, bg_image: str | None, dest: Path, text: str | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Background: use best scene image, else gradient
    if bg_image and Path(bg_image).exists():
        img = Image.open(bg_image).convert("RGB")
        img.thumbnail((W * 2, H * 2))
        # Cover-crop
        scale = max(W / img.width, H / img.height)
        img = img.resize((int(img.width * scale), int(img.height * scale)))
        x = (img.width - W) // 2
        y = (img.height - H) // 2
        img = img.crop((x, y, x + W, y + H))
    else:
        img = Image.new("RGB", (W, H), (20, 30, 60))
    # Darken for text contrast
    overlay = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.blend(img, overlay, 0.45)
    d = ImageDraw.Draw(img)

    # Accent bar
    d.rectangle([0, H - 26, W, H], fill=(255, 60, 60))

    # Thumbnail text: short, punchy, max ~5 words
    words = (text or topic).split()
    # Prefer the most informative words
    title_words = words[:5] if len(words) > 5 else words
    title = " ".join(title_words).upper()
    if len(title) > 42:
        title = title[:42].rsplit(" ", 1)[0] + "…"

    # Auto-fit font
    size = 110
    while size > 40:
        font = _font(size)
        if d.textlength(title, font=font) < W * 0.9:
            break
        size -= 8
    # Wrap to 2 lines if needed
    lines = [title]
    if d.textlength(title, font=font) >= W * 0.9:
        mid = len(title) // 2
        split = title.rfind(" ", 0, mid)
        if split > 0:
            lines = [title[:split], title[split + 1:]]
    line_h = int(size * 1.05)
    y0 = (H - len(lines) * line_h) // 2 - 10
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=font)
        x = (W - tw) / 2
        y = y0 + i * line_h
        # Stroke for punch
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
            d.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        d.text((x, y), line, font=font, fill=(255, 255, 255))

    # Small channel tag
    tag_font = _font(28, bold=False)
    tag = "STORYTELLER"
    tw = d.textlength(tag, font=tag_font)
    d.text(((W - tw) / 2, 30), tag, font=tag_font, fill=(220, 220, 220))

    img.save(dest, "JPEG", quality=90)
    return dest
