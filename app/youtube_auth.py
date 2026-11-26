"""One-time YouTube OAuth login. Run: python -m app.youtube_auth

Requires credentials.json (Google Cloud Console → YouTube Data API v3 → OAuth Desktop).
Creates token.json used by app/youtube.py. Never commit token.json.
"""
from __future__ import annotations

from google_auth_oauthlib.flow import InstalledAppFlow

from .config import settings
from .youtube import SCOPES


def main():
    if not settings.credentials_file.exists():
        print(f"❌ {settings.credentials_file} not found.")
        print("   1. console.cloud.google.com → new project")
        print("   2. Enable 'YouTube Data API v3'")
        print("   3. Credentials → OAuth 2.0 → Desktop app → download JSON")
        print(f"   4. Upload it to Colab / project root as: {settings.credentials_file}")
        print("   5. Re-run: python -m app.youtube_auth")
        return
    flow = InstalledAppFlow.from_client_secrets_file(str(settings.credentials_file), SCOPES)
    try:
        # Colab supports localhost proxy; fall back to console if not
        creds = flow.run_local_server(port=0)
    except Exception:
        creds = flow.run_console()
    settings.token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"✅ Saved {settings.token_file}. YouTube upload is ready!")


if __name__ == "__main__":
    main()
