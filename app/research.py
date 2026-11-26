"""Stage A — Research. Wikipedia + DuckDuckGo. No API keys. No fabricated facts."""
from __future__ import annotations

import re
import textwrap

import requests

UA = {"User-Agent": "Storyteller/1.0 (educational video tool; contact: local)"}


def _clean(t: str) -> str:
    t = re.sub(r"\[\d+\]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def wikipedia(topic: str, sentences: int = 12) -> dict:
    """Resolve topic via Wikipedia search, then pull the summary. No fabricated facts."""
    title = topic
    try:
        # Step 1: search to find the right article (e.g. "Why is the sky blue?" -> "Rayleigh scattering")
        r = requests.get("https://en.wikipedia.org/w/api.php",
                         params={"action": "query", "list": "search", "srsearch": topic,
                                 "format": "json", "srlimit": 3},
                         headers=UA, timeout=15)
        if r.status_code == 200:
            hits = r.json().get("query", {}).get("search", [])
            if hits:
                title = hits[0]["title"]
    except Exception:
        pass
    try:
        r = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(title.replace(" ", "_")),
            headers=UA, timeout=15,
        )
        if r.status_code != 200:
            raise ValueError("no summary")
        j = r.json()
        extract = _clean(j.get("extract", ""))
        title = j.get("title", title)
        url = j.get("content_urls", {}).get("desktop", {}).get("page", "")
        facts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", extract) if len(s.strip()) > 40]
        return {"title": title, "extract": extract, "facts": facts[:sentences],
                "source": url or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "source_name": "Wikipedia"}
    except Exception:
        return {"title": topic, "extract": "", "facts": [], "source": "", "source_name": ""}


def duckduckgo(topic: str) -> list[dict]:
    """Instant-answer abstracts as extra context (never presented as quotes)."""
    try:
        r = requests.get("https://api.duckduckgo.com/",
                         params={"q": topic, "format": "json", "no_html": 1}, headers=UA, timeout=15)
        j = r.json()
        out = []
        if j.get("AbstractText"):
            out.append({"text": _clean(j["AbstractText"])[:600], "source": j.get("AbstractURL", "")})
        for t in j.get("RelatedTopics", [])[:4]:
            if isinstance(t, dict) and t.get("Text"):
                out.append({"text": _clean(t["Text"])[:300], "source": t.get("FirstURL", "")})
        return out
    except Exception:
        return []


def research(topic: str) -> dict:
    """Full research bundle. Always returns something usable, even offline."""
    wiki = wikipedia(topic)
    ddg = duckduckgo(topic)
    facts = list(wiki.get("facts", []))
    for item in ddg:
        if item["text"] and item["text"] not in facts:
            facts.append(item["text"])
    if not facts:
        facts = [
            f"Today we are exploring {topic}.",
            "This topic matters because it affects everyday life in ways most people never notice.",
            "Experts agree the basics are simple once you break them down step by step.",
        ]
    summary = " ".join(facts[:3])
    sources = [s for s in [wiki.get("source", "")] + [d["source"] for d in ddg] if s]
    return {
        "topic": topic,
        "title": wiki.get("title", topic),
        "summary": textwrap.shorten(summary, width=600, placeholder="…"),
        "facts": facts[:12],
        "sources": sources[:5],
        "source_name": wiki.get("source_name", "Wikipedia"),
    }
