"""Stage H — YouTube Data API v3 upload (OAuth 2.0). Never publishes without approval."""
from __future__ import annotations

from pathlib import Path

from .config import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def is_configured() -> bool:
    return settings.credentials_file.exists() and settings.token_file.exists()


def get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(settings.token_file), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: Path, thumbnail_path: Path, meta: dict) -> dict:
    """Upload video + thumbnail. Returns {video_id, url}. Raises on failure."""
    from googleapiclient.http import MediaFileUpload

    yt = get_service()
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"][:5000],
            "tags": meta.get("tags", []),
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": meta.get("privacy", "unlisted"),
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True,
                            mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
    video_id = resp["id"]
    # Thumbnail
    try:
        yt.thumbnails().set(videoId=video_id,
                            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")).execute()
    except Exception:
        pass  # video is up; thumbnail can be set manually
    return {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}


def manual_package(video_path: Path, thumbnail_path: Path, meta: dict, dest_dir: Path) -> dict:
    """Fallback when API isn't configured: a ready-to-upload folder."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "description.txt").write_text(
        f"Title:\n{meta['title']}\n\nDescription:\n{meta['description']}\n\n"
        f"Tags:\n{', '.join(meta.get('tags', []))}\n\n"
        f"Category: {meta.get('category', 'Education')}\n"
        f"Audience: Not made for kids\n"
        f"Privacy: {meta.get('privacy', 'unlisted')}\n",
        encoding="utf-8",
    )
    (dest_dir / "upload_checklist.txt").write_text(
        "1. Go to youtube.com/upload\n"
        "2. Upload the MP4 file\n"
        "3. Paste title + description from description.txt\n"
        "4. Upload the thumbnail JPG\n"
        "5. Set visibility (Unlisted recommended for review)\n"
        "6. Publish!\n",
        encoding="utf-8",
    )
    return {"manual": True, "dir": str(dest_dir)}
