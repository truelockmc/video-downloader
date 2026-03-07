#!/usr/bin/env python3
"""
Helper Functions: ffmpeg-check/install, network speed test, config,
Videasy-Header builder and cleanup helper.
"""

import configparser
import glob
import os
import platform
import re
import shutil
import subprocess
import sys
import time

import requests
from PyQt6 import QtWidgets

CONFIG_FILE = "download_config.ini"
TEST_URL = (
    "https://ipv4.download.thinkbroadband.com/1MB.zip"  # 1MB test file for speed test
)


def check_ffmpeg():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except Exception:
        QtWidgets.QMessageBox.warning(
            None,
            "ffmpeg required",
            "This program requires ffmpeg to merge file formats.",
        )
        return False


def install_ffmpeg():
    os_name = platform.system().lower()
    installed = False
    error_msg = ""

    try:
        if os_name == "windows":
            # Try winget first
            if shutil.which("winget"):
                subprocess.run(
                    ["winget", "install", "Gyan.FFmpeg.Essentials", "-e", "--silent"],
                    check=True,
                )
                installed = True
            # Try Chocolatey if winget is not available
            elif shutil.which("choco"):
                subprocess.run(["choco", "install", "ffmpeg", "-y"], check=True)
                installed = True
            else:
                error_msg = (
                    "Automatic ffmpeg installation failed: Neither winget nor Chocolatey was found.\n"
                    "Please install ffmpeg manually from https://ffmpeg.org/download.html or add it to your PATH."
                )
        elif os_name == "darwin":  # macOS
            if shutil.which("brew"):
                subprocess.run(["brew", "install", "ffmpeg"], check=True)
                installed = True
            else:
                error_msg = (
                    "Homebrew is not installed. Please install Homebrew from https://brew.sh/ and then run 'brew install ffmpeg', "
                    "or download ffmpeg manually from https://ffmpeg.org/download.html."
                )
        elif os_name == "linux":
            # Try most common package managers
            if shutil.which("apt"):
                subprocess.run(["sudo", "apt", "update"], check=True)
                subprocess.run(["sudo", "apt", "install", "-y", "ffmpeg"], check=True)
                installed = True
            elif shutil.which("dnf"):
                subprocess.run(["sudo", "dnf", "install", "-y", "ffmpeg"], check=True)
                installed = True
            elif shutil.which("pacman"):
                subprocess.run(
                    ["sudo", "pacman", "-Sy", "ffmpeg", "--noconfirm"], check=True
                )
                installed = True
            else:
                error_msg = (
                    "No supported package manager found. Please install ffmpeg using your distribution's package manager, "
                    "or download from https://ffmpeg.org/download.html."
                )
        else:
            error_msg = f"Unsupported OS: {os_name}. Please install ffmpeg from https://ffmpeg.org/download.html."

        if installed:
            QtWidgets.QMessageBox.information(
                None,
                "Success",
                "ffmpeg was successfully installed. Please restart the program.",
            )
        else:
            QtWidgets.QMessageBox.critical(None, "Error", error_msg)
            sys.exit(1)
    except Exception as e:
        QtWidgets.QMessageBox.critical(
            None,
            "Error",
            f"ffmpeg installation failed:\n{e}\n\nPlease install ffmpeg manually from https://ffmpeg.org/download.html.",
        )
        sys.exit(1)


def network_speed_test():
    try:
        start_time = time.time()
        response = requests.get(TEST_URL, stream=True, timeout=10)
        total = 0
        chunk_size = 1024 * 1024  # 1 MB
        for chunk in response.iter_content(chunk_size=chunk_size):
            total += len(chunk)
            break
        duration = time.time() - start_time
        if duration == 0:
            duration = 0.1
        speed = (total / 1024 / 1024) / duration
        return speed
    except Exception:
        return 1.0


def load_or_create_config():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if "DownloadOptions" in config:
            return config
    speed = network_speed_test()
    if speed >= 5:
        concurrent_fragments = "10"
        http_chunk_size = "4194304"
        max_concurrent = "5"
    elif speed >= 2:
        concurrent_fragments = "5"
        http_chunk_size = "2097152"
        max_concurrent = "3"
    else:
        concurrent_fragments = "3"
        http_chunk_size = "1048576"
        max_concurrent = "2"
    config["DownloadOptions"] = {
        "concurrent_fragment_downloads": concurrent_fragments,
        "http_chunk_size": http_chunk_size,
        "download_folder": os.path.expanduser("~"),
        "max_concurrent_downloads": max_concurrent,
    }
    with open(CONFIG_FILE, "w") as configfile:
        config.write(configfile)
    return config


def format_filesize(size_bytes) -> str:
    """Convert a byte count to a human-readable string (e.g. '4.2 MB')."""
    if not size_bytes:
        return "Unknown"
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def friendly_error(raw: str) -> str:
    """
    Map raw yt-dlp / network exception strings to short, human-readable messages.
    Falls back to a trimmed version of the original if nothing matches.
    """
    s = raw.lower()

    # HTTP / access errors
    if "403" in s or "forbidden" in s:
        return "Access denied (403), the site blocked the request."
    if "401" in s or "unauthorized" in s:
        return "Login required, please provide credentials."
    if "404" in s or "not found" in s:
        return "Video not found (404), the URL may be wrong or deleted."
    if "429" in s or "too many requests" in s:
        return "Rate-limited (429), too many requests. Try again later."
    if "ssl" in s or "certificate" in s:
        return "SSL/certificate error, check your network or proxy settings."

    # Content availability
    if "private video" in s or "private" in s and "video" in s:
        return "Private video, you don't have access."
    if "members-only" in s or "members only" in s:
        return "Members-only content, login or subscription required."
    if "age" in s and ("restrict" in s or "limit" in s or "gate" in s):
        return "Age-restricted content, login with a verified account."
    if "unavailable" in s or "not available" in s:
        return "Video unavailable in your region or has been removed."
    if "removed" in s or "deleted" in s or "terminated" in s:
        return "This video has been removed or the account was terminated."
    if "copyright" in s:
        return "Video blocked due to a copyright claim."
    if "live" in s and ("not yet" in s or "upcoming" in s or "premiere" in s):
        return "This stream hasn't started yet (upcoming/premiere)."
    if "live event" in s or "this live stream" in s:
        return "Live stream, live downloads are not supported."

    # Format / extraction
    if "no video formats" in s or "no formats" in s:
        return "No downloadable formats found for this URL."
    if "unsupported url" in s:
        return "Unsupported URL, this site is not supported."
    if "unable to extract" in s or "could not extract" in s:
        return "Could not extract video info, the page structure may have changed."
    if "extractor" in s and "error" in s:
        return "Extractor error, yt-dlp may need an update."

    # Network
    if "timed out" in s or "timeout" in s:
        return "Connection timed out, check your internet connection."
    if "connection" in s and ("refused" in s or "reset" in s or "error" in s):
        return "Network connection error, check your internet connection."
    if "name or service not known" in s or "getaddrinfo" in s:
        return "DNS error, could not resolve hostname."

    # ffmpeg
    if "ffmpeg" in s and ("not found" in s or "no such" in s):
        return "ffmpeg not found, please install ffmpeg and restart."
    if "ffmpeg" in s:
        return "ffmpeg error during post-processing."

    # Cancelled
    if "cancelled" in s:
        return "Download was cancelled."

    # Generic fallback, strip yt-dlp prefix noise and cap length
    cleaned = raw
    for prefix in ("[yt-dlp error]", "error:", "warning:", "[error]"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned[:120] + ("…" if len(cleaned) > 120 else "")


def get_videasy_headers():
    """
    The special headers that are needed for Videasy.
    These are only used if needed (Retry after 403).
    """
    return {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://player.videasy.net",
        "Referer": "https://player.videasy.net/",
    }


def cleanup_download_folder(folder):
    """
    Remove common temporary/partial files in the download folder.
    Currently removes:
      - files ending with '.part'
      - files matching '*.part.*'
      - files ending with '.part.tmp' (just in case)
    Returns a list of removed file paths.
    """
    removed = []
    try:
        if not folder:
            return removed
        folder = os.path.expanduser(folder)
        if not os.path.isdir(folder):
            return removed
        patterns = ["*.part", "*.part.*", "*.part.tmp", "*.tmp", "*.ytdl"]
        for pat in patterns:
            full_pat = os.path.join(folder, pat)
            for fp in glob.glob(full_pat):
                try:
                    os.remove(fp)
                    removed.append(fp)
                except Exception:
                    # best-effort: ignore removal errors
                    pass
    except Exception:
        # best-effort, never raise here
        pass
    return removed


# -------------------------
# Filename helpers
# -------------------------
_INVALID_FN_CHARS = r'<>:"/\\|?*\0'  # include NUL
_INVALID_FN_RE = re.compile(r'[<>:"/\\|?*\x00]')


def sanitize_filename(name: str, max_length: int = 240) -> str:
    """
    Remove or replace characters invalid in filenames and trim length.
    """
    if not name:
        return "download"
    # Replace invalid chars with underscore
    name = _INVALID_FN_RE.sub("_", name)
    # Trim whitespace and collapse multiple spaces
    name = re.sub(r"\s+", " ", name).strip()
    # On some filesystems, filenames must be shorter. Trim to max_length.
    if len(name) > max_length:
        name = name[:max_length].rstrip()
    return name


def unique_filename(folder: str, base_name: str, ext: str) -> str:
    """
    Ensure a unique filename in folder.
    base_name: without extension
    ext: extension WITHOUT leading dot, e.g. 'mp4' or 'mkv'
    Returns full path to unique filename (folder + base + maybe ' (n)' + .ext)
    """
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        # Ensure folder exists or fallback to current dir
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            folder = os.getcwd()
    base = sanitize_filename(base_name)
    if ext:
        ext = ext.lstrip(".")
    candidate = f"{base}.{ext}" if ext else base
    full = os.path.join(folder, candidate)
    i = 1
    while os.path.exists(full):
        candidate = f"{base} ({i})"
        candidate_with_ext = f"{candidate}.{ext}" if ext else candidate
        full = os.path.join(folder, candidate_with_ext)
        i += 1
    return full
