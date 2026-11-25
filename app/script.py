"""Stage B — Scriptwriting. Template engine (zero keys) + optional LLM upgrade."""
from __future__ import annotations

import os
import re
import textwrap

HOOKS = [
    "You will never look at {topic} the same way again. Here is why.",
    "Stop scrolling. In the next {mins} minutes, you will understand {topic} better than 90% of people.",
    "What if everything you thought about {topic} was only half the story?",
    "This is the simplest explanation of {topic} you will ever hear — and it changes everything.",
]

CLOSINGS = [
    "So now you know the real story behind {topic}. If this helped you, share it with someone who needs to hear it.",
    "That is {topic} in a nutshell. Subscribe for more simple explanations of complicated things.",
    "Now you understand {topic}. The next time someone asks, you will have the answer.",
]

CTAS = [
    "Like and subscribe for more videos like this.",
    "Hit subscribe — we explain one big idea every week, simply.",
    "Comment below: what should we explain next?",
]

# Visual keywords per generic scene type (used for image search)
VISUAL_HINTS = [
    "{topic}", "science explained", "history timeline", "nature close up",
    "people learning", "technology future", "world map", "daily life",
]


def _llm_script(topic: str, facts: list[str], duration_sec: int, language: str) -> str | None:
    """Try OpenAI then Gemini. Returns None if no key / failure (template takes over)."""
    facts_txt = "\n".join(f"- {f}" for f in facts[:8])
    prompt = (
        f"Write a YouTube narration script about: {topic}\n"
        f"Target length: ~{duration_sec} seconds spoken (about {int(duration_sec * 2.5)} words).\n"
        f"Language: {language}. Use ONLY these verified facts, do not invent statistics or quotes:\n{facts_txt}\n"
        "Structure: hook, 4-6 scenes, closing + soft call to action. Plain sentences, no markup."
    )
    try:
        if os.getenv("OPENAI_API_KEY"):
            import requests
            r = requests.post("https://api.openai.com/v1/chat/completions", timeout=30,
                              headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"},
                              json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]})
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        if os.getenv("GEMINI_API_KEY"):
            import requests
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={os.getenv('GEMINI_API_KEY')}",
                timeout=30, json={"contents": [{"parts": [{"text": prompt}]}]})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        pass
    return None


def build_script(topic: str, research: dict, duration_sec: int, language: str = "en",
                 description: str = "") -> dict:
    """Returns {full_text, scenes:[{n, narration, visual_query, duration_sec}]}."""
    facts = research.get("facts", [])
    llm = _llm_script(topic, facts, duration_sec, language)
    mins = max(1, round(duration_sec / 60))

    if llm:
        # Split LLM output into scenes by paragraph
        paras = [p.strip() for p in re.split(r"\n\s*\n", llm) if p.strip()]
        scenes = []
        per = max(4, duration_sec // max(1, len(paras)))
        for i, p in enumerate(paras):
            scenes.append({"n": i + 1, "narration": textwrap.shorten(p, width=400, placeholder="…"),
                           "visual_query": VISUAL_HINTS[i % len(VISUAL_HINTS)].format(topic=topic),
                           "duration_sec": per})
        full = llm
        engine = "llm"
    else:
        # Template engine — deterministic, fact-grounded, duration-aware
        hook = HOOKS[hash(topic) % len(HOOKS)].format(topic=topic, mins=mins)
        closing = CLOSINGS[hash(topic + "c") % len(CLOSINGS)].format(topic=topic)
        cta = CTAS[hash(topic + "t") % len(CTAS)]
        n_scenes = max(4, min(10, duration_sec // 12))
        # Distribute facts across scenes; pad with connective tissue (no new facts invented)
        scenes = [{"n": 1, "narration": hook,
                   "visual_query": topic, "duration_sec": max(4, duration_sec // 12)}]
        per = max(4, (duration_sec - 8) // max(1, n_scenes))
        for i in range(n_scenes):
            fact = facts[i % len(facts)] if facts else f"Let us look closer at {topic}."
            narration = fact if fact.endswith((".", "!", "?")) else fact + "."
            if description and i == 0:
                narration = description.strip() + " " + narration
            scenes.append({"n": i + 2, "narration": narration,
                           "visual_query": VISUAL_HINTS[i % len(VISUAL_HINTS)].format(topic=topic),
                           "duration_sec": per})
        scenes.append({"n": len(scenes) + 1, "narration": closing + " " + cta,
                       "visual_query": topic, "duration_sec": max(4, duration_sec // 12)})
        full = "\n\n".join(s["narration"] for s in scenes)
        engine = "template"

    # Normalize durations to target
    total = sum(s["duration_sec"] for s in scenes) or 1
    for s in scenes:
        s["duration_sec"] = max(3, round(s["duration_sec"] / total * duration_sec))
    return {"full_text": full, "scenes": scenes, "engine": engine, "word_count": len(full.split())}
