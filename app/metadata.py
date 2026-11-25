"""Stage G — YouTube metadata. Honest, non-clickbait, SEO-friendly."""
from __future__ import annotations

import re


def _slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:50]


def build_metadata(topic: str, research: dict, duration_sec: int, fmt: str, language: str = "en") -> dict:
    title = topic.strip()
    if not title.endswith("?"):
        title = title[0].upper() + title[1:] if title else topic
    # Keep under 60 chars for YouTube display
    if len(title) > 60:
        title = title[:57].rsplit(" ", 1)[0] + "…"

    summary = research.get("summary", "")
    sources = research.get("sources", [])
    src_lines = "\n".join(f"- {s}" for s in sources) if sources else "- Wikipedia (see description)"

    description = (
        f"{title}\n\n"
        f"{summary}\n\n"
        f"In this video we break down {topic} step by step — the key facts, the simple explanation, and why it matters.\n\n"
        f"Sources:\n{src_lines}\n\n"
        f"Made with Storyteller (open-source video studio).\n"
        f"#education #{_slug(topic)} #explained"
    )

    # Tags: topic words + evergreen YouTube tags
    base_tags = [topic, f"{topic} explained", "education", "learn", "explained simply",
                 "how it works", "documentary", "knowledge"]
    tags = []
    for t in base_tags:
        t = t.strip()
        if t and t not in tags:
            tags.append(t)
    hashtags = [f"#{_slug(topic)}", "#education", "#explained", "#learnontiktok" if fmt == "9:16" else "#youtube"]

    return {
        "title": title,
        "description": description,
        "tags": tags[:15],
        "hashtags": hashtags,
        "category": "Education",
        "audience": "not_made_for_kids",
        "privacy": "unlisted",  # safe default — user flips to public after review
        "thumbnail_text": " ".join(topic.split()[:4]).upper(),
    }
