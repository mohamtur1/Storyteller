# Storyteller — One-Button YouTube Video Studio

Turn a **topic** into a finished, publishable YouTube video — from your Android phone.

```
Topic → Research → Script → Images → Narration → Subtitles → Video → Thumbnail → Metadata → Preview → YouTube
```

## How it works (the 2-year-old version)

Imagine you want to make a little movie about "Why is the sky blue?"

1. **You type one sentence** on your phone: *"Why is the sky blue?"*
2. **The computer does the homework** — it reads Wikipedia and learns the facts.
3. **It writes a story** — like a teacher explaining it in simple words, scene by scene.
4. **It finds pictures** — one picture for each part of the story.
5. **A robot voice reads the story aloud** — you don't need to record anything.
6. **It puts it all together** — pictures + voice + words at the bottom = a real video!
7. **It makes a cover picture** (thumbnail) so people click on it.
8. **You watch it, you like it, you press "Publish"** — and it goes to YouTube.

Your phone is just the **remote control**. The big computer (Google Colab) does all the heavy lifting.

## Quick start

### Option A — Run it here / on any computer (recommended for testing)

```bash
pip install -r requirements.txt
python run.py
# Open http://localhost:8000 on your phone (same Wi-Fi) or computer
```

### Option B — Google Colab (free, no install)

1. Open `notebooks/Storyteller_Colab.ipynb` in Google Colab
2. Run all cells — it installs everything and gives you a public link
3. Open that link on your phone's Chrome

### Option C — Docker

```bash
docker compose up
# Open http://localhost:8000
```

## What you get

- **Mobile-first web app** — works on itel A60 / any low-spec Android in Chrome
- **Zero-config demo mode** — works with no API keys (Wikipedia + Openverse images + Edge TTS)
- **16:9 landscape or 9:16 vertical (Shorts/Reels)**
- **60s / 2min / 5min / 10min** durations
- **Multi-voice narration** (Piper / Edge TTS / gTTS fallbacks)
- **Auto subtitles (.srt + burned-in)**
- **1280×720 thumbnail generator**
- **YouTube metadata (title, description, tags, hashtags)**
- **YouTube Data API v3 upload** (OAuth 2.0) — or manual-upload package if no credentials
- **Google Drive archiving** — every project saved under `YouTubeStudio/Projects/<Name>/`
- **Resume support** — interrupted projects pick up where they left off
- **Project state machine** — retry only the failed stage

## Project structure

```
Storyteller/
├── app/
│   ├── main.py          # FastAPI app + API routes
│   ├── config.py        # Settings / env
│   ├── store.py         # Project state + resume
│   ├── research.py      # Stage A — Wikipedia + DuckDuckGo
│   ├── script.py        # Stage B — script + scene breakdown
│   ├── images.py        # Stage C — Openverse/Wikimedia + PIL fallback
│   ├── tts.py           # Stage D — Piper/Edge/gTTS
│   ├── video.py         # Stage E — FFmpeg assembly + subtitles
│   ├── thumbnail.py     # Stage F — 1280×720 thumbnail
│   ├── metadata.py      # Stage G — title/desc/tags
│   ├── youtube.py       # Stage H — YouTube Data API upload
│   └── drive.py         # Google Drive / local archiving
├── static/
│   ├── index.html       # Mobile-first UI
│   ├── style.css
│   └── app.js
├── notebooks/
│   └── Storyteller_Colab.ipynb
├── projects/            # Local output (gitignored)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── run.py
```

## Configuration (all optional)

Copy `.env.example` to `.env` and fill in what you have. **Everything works without keys.**

| Variable | What it's for | Free? |
|---|---|---|
| `OPENAI_API_KEY` | Smarter scripts (optional) | Paid — skip it |
| `GEMINI_API_KEY` | Smarter scripts (optional) | Free tier available |
| `PEXELS_API_KEY` | Better stock photos (optional) | Free |
| `YOUTUBE_CLIENT_ID/SECRET` | Auto-upload to YouTube | Free (Google Cloud) |
| `DRIVE_FOLDER_ID` | Auto-archive to Drive | Free |

## YouTube upload setup (5 minutes)

1. Go to [Google Cloud Console](https://console.cloud.google.com) → create a project
2. Enable **YouTube Data API v3**
3. Create **OAuth 2.0 credentials** → Desktop app → download `credentials.json`
4. Put it in the project root, run `python -m app.youtube_auth` once to log in
5. Done — the app will offer "Publish to YouTube" after you approve the preview

No credentials? No problem — the app always produces a **manual-upload package** (MP4 + thumbnail + description.txt) you can upload from your phone in 2 minutes.

## Google Drive setup

- **In Colab:** the notebook mounts your Drive automatically. Projects land in `MyDrive/YouTubeStudio/`
- **Locally:** set `DRIVE_FOLDER_ID` or just use the local `projects/` folder and copy it to Drive

## Free-tier limits (be honest)

- **Colab free:** ~12h session, may disconnect. Projects resume from Drive.
- **YouTube API:** 10,000 quota units/day (~6 uploads/day). Manual upload has no limit.
- **Edge TTS:** free, no quota. Piper: fully offline.
- **Images:** Openverse/Wikimedia are free with attribution.

## Testing

```bash
# Health check
curl http://localhost:8000/api/health

# Create a project (demo, no keys needed)
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"topic":"Why is the sky blue?","duration_sec":60,"format":"16:9"}'

# Watch progress
curl http://localhost:8000/api/projects/<id>
```

## License

MIT — free and open source. Images are credited per-source in each project's `Metadata/credits.txt`.
