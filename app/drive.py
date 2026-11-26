"""Google Drive archiving. Local folder always works; Drive upload when mounted (Colab)."""
from __future__ import annotations

from pathlib import Path

from .config import settings


def _colab_drive_mounted() -> bool:
    return Path("/content/drive/MyDrive").exists()


def archive(project_dir: Path, drive_root: Path | None = None) -> dict:
    """Copy project into Drive mount (Colab: /content/drive/MyDrive/YouTubeStudio).

    Returns {drive_url, path, on_drive}. If no Drive mount, returns local path.
    """
    target_root = drive_root or Path("/content/drive/MyDrive/YouTubeStudio/Projects")
    try:
        if _colab_drive_mounted():
            dest = target_root / project_dir.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(project_dir, dest,
                            ignore=shutil.ignore_patterns("_build", "__pycache__"))
            folder_id = settings.drive_folder_id or "your-drive-folder"
            return {
                "drive_url": f"https://drive.google.com/drive/folders/{folder_id}",
                "path": str(dest),
                "on_drive": True,
                "note": "Open Google Drive on your phone → YouTubeStudio → Projects → this project folder",
            }
    except Exception:
        pass
    return {"drive_url": "", "path": str(project_dir), "on_drive": False,
            "note": "Drive not mounted — files are local to this Colab session only."}


def drive_folder_link(folder_id: str | None = None) -> str:
    """Public-friendly link to the Drive folder where projects live."""
    fid = folder_id or settings.drive_folder_id
    if fid:
        return f"https://drive.google.com/drive/folders/{fid}"
    return "https://drive.google.com/drive/my-drive"
