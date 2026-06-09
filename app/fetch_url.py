"""Pull audio from a media URL (YouTube, podcasts, ~1000 sites) via yt-dlp.

Two steps, kept separate so the duration cap is enforced from cheap metadata
*before* we download anything heavy:
  probe_url(url)      -> (duration_ms, title)   — metadata only, no download
  download_audio(url) -> local mp3 path         — bestaudio, extracted via ffmpeg
"""
import glob
import os
import tempfile
import uuid

import yt_dlp

_QUIET = {"quiet": True, "no_warnings": True, "noprogress": True}


def probe_url(url: str) -> tuple[int, str]:
    """Return (duration_ms, title) from metadata only. Raises on a bad URL."""
    with yt_dlp.YoutubeDL({**_QUIET, "skip_download": True}) as y:
        info = y.extract_info(url, download=False)
    # playlists/channels carry no single duration — reject them
    duration = info.get("duration")
    if not duration:
        raise ValueError("no playable single track at that URL")
    title = info.get("title") or "Untitled"
    return int(duration * 1000), title


def download_audio(url: str) -> str:
    """Download bestaudio and extract it to a temp .mp3; return the file path."""
    stem = os.path.join(tempfile.gettempdir(), f"url_{uuid.uuid4().hex}")
    opts = {
        **_QUIET,
        "format": "bestaudio/best",
        "outtmpl": f"{stem}.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
    }
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([url])
    matches = glob.glob(f"{stem}.mp3")
    if not matches:
        # fall back to whatever extension landed, if the post-processor was skipped
        matches = glob.glob(f"{stem}.*")
    if not matches:
        raise RuntimeError("download produced no file")
    return matches[0]
