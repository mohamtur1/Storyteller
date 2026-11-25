"""Storyteller launcher — `python run.py` and you're live."""
import uvicorn

from app.config import settings
from app.main import app

if __name__ == "__main__":
    print(f"\n🎬 Storyteller is live at http://{settings.host}:{settings.port}")
    print("   Open it on your phone (same Wi-Fi) or computer.\n")
    uvicorn.run(app, host=settings.host, port=settings.port)
