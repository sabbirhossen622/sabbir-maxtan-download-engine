
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

app = FastAPI(
    title="SABBIR MAXTAN Download Engine",
    version="2.0.0"
)

# শুধু নির্ধারিত প্ল্যাটফর্মের লিংক গ্রহণ করবে।
ALLOWED_HOSTS = {
    "youtube.com", "youtu.be", "youtube-nocookie.com",
    "facebook.com", "fb.watch",
    "tiktok.com",
    "instagram.com",
}

# একসঙ্গে একাধিক বড় ডাউনলোডে সার্ভার যেন অতিরিক্ত চাপে না পড়ে।
download_lock = threading.Lock()


class DownloadRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    quality: Literal["360", "720", "1080"] = "720"


def validate_url(url: str):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if parsed.scheme != "https":
            raise ValueError()

        if not any(
            host == domain or host.endswith("." + domain)
            for domain in ALLOWED_HOSTS
        ):
            raise ValueError()

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="শুধু সমর্থিত HTTPS প্ল্যাটফর্মের URL দিন।"
        )


def base_options():
    return {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 1,
        "max_filesize": 500 * 1024 * 1024,
    }


@app.get("/")
def home():
    return {
        "app": "SABBIR MAXTAN Download Engine",
        "status": "online",
        "version": "2.0.0"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/download/status")
def download_status():
    return {
        "status": "ready",
        "message": "Download API available"
    }


@app.post("/api/info")
def video_info(req: DownloadRequest):
    validate_url(req.url)

    try:
        with yt_dlp.YoutubeDL(base_options()) as ydl:
            info = ydl.extract_info(req.url, download=False)

        formats = []
        seen = set()

        for item in info.get("formats", []):
            height = item.get("height")
            if height and height not in seen:
                seen.add(height)
                formats.append(height)

        return {
            "title": info.get("title", "Video"),
            "duration": info.get("duration"),
            "available_heights": sorted(formats, reverse=True),
            "requested_quality": req.quality
        }

    except Exception:
        raise HTTPException(
            status_code=422,
            detail="ভিডিও তথ্য পাওয়া যায়নি। লিংক ও সোর্সের অনুমতি যাচাই করুন।"
        )


@app.post("/api/download")
def download_video(req: DownloadRequest):
    validate_url(req.url)

    # এই MVP-তে একবারে একটি ডাউনলোড।
    if not download_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="অন্য একটি ডাউনলোড চলছে। পরে চেষ্টা করুন।"
        )

    temp_dir = tempfile.mkdtemp(prefix="maxtan_")
    output_template = str(Path(temp_dir) / "video.%(ext)s")

    max_height = int(req.quality)

    options = {
        **base_options(),
        "format": (
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": output_template,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(req.url, download=True)

        files = [
            p for p in Path(temp_dir).iterdir()
            if p.is_file() and p.stat().st_size > 0
        ]

        if not files:
            raise RuntimeError("No output file")

        file_path = files[0]
        title = info.get("title", "video")
        safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title)
        safe_title = safe_title.strip(" .")[:100] or "video"
        filename = f"{safe_title}{file_path.suffix}"

        def cleanup():
            import shutil
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            finally:
                download_lock.release()

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/octet-stream",
            background=BackgroundTask(cleanup)
        )

    except Exception:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        download_lock.release()

        raise HTTPException(
            status_code=422,
            detail=(
                "ডাউনলোড ব্যর্থ হয়েছে। লিংক, অ্যাক্সেস, "
                "উপলভ্য কোয়ালিটি ও সার্ভার লগ পরীক্ষা করুন।"
            )
        )
