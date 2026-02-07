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
            pkg_cmds = []
            if shutil.which("apt"):
                pkg_cmds = [
                    ("apt update", "apt install -y ffmpeg")
                ]
            elif shutil.which("dnf"):
                pkg_cmds = [
                    ("", "dnf install -y ffmpeg")
                ]
            elif shutil.which("pacman"):
<<<<<<< Updated upstream
                pkg_cmds = [
                    ("pacman -Sy", "pacman -S --noconfirm ffmpeg")
                ]

            if not pkg_cmds:
=======
                subprocess.run(
                    ["sudo", "pacman", "-Sy", "ffmpeg", "--noconfirm"], check=True
                )
                installed = True
            else:
>>>>>>> Stashed changes
                error_msg = (
                    "No supported package manager found. Please install ffmpeg using your distribution's package manager, "
                    "or download from https://ffmpeg.org/download.html."
                )
            else:
                is_root = os.name != "nt" and getattr(os, "geteuid", lambda: 1)() == 0
                for update_cmd, install_cmd in pkg_cmds:
                    try:
                        if is_root:
                            if update_cmd:
                                subprocess.run(update_cmd.split(), check=True)
                            subprocess.run(install_cmd.split(), check=True)
                            installed = True
                            break
                        elif shutil.which("pkexec"):
                            full_cmd = " && ".join([c for c in (update_cmd, install_cmd) if c])
                            subprocess.run(["pkexec", "bash", "-c", full_cmd], check=True)
                            installed = True
                            break
                        else:
                            cmd_lines = []
                            if update_cmd:
                                cmd_lines.append(update_cmd)
                            cmd_lines.append(install_cmd)
                            cmd_text = " && ".join(cmd_lines)
                            QtWidgets.QMessageBox.information(
                                None,
                                "Manual installation required",
                                f"Automatic ffmpeg installation requires elevated previleges.\n\n"
                                f"Run this in your Terminal:\n\n{cmd_text}\n\n"
                                "The command has been pasted into your clipboard."
                            )
                            try:
                                QtWidgets.QApplication.clipboard().setText(cmd_text)
                            except Exception:
                                pass
                            installed = False
                            break
                    except subprocess.CalledProcessError as e:
                        continue

        else:
            error_msg = f"Unsupported OS: {os_name}. Please install ffmpeg from https://ffmpeg.org/download.html."

        if installed:
            QtWidgets.QMessageBox.information(
                None,
                "Success",
                "ffmpeg was successfully installed. Please restart the program.",
            )
            sys.exit(0)

        else:
<<<<<<< Updated upstream
            if error_msg:
                QtWidgets.QMessageBox.critical(
                    None, "Error",
                    error_msg
                )
=======
            QtWidgets.QMessageBox.critical(None, "Error", error_msg)
            sys.exit(1)
>>>>>>> Stashed changes
    except Exception as e:
        QtWidgets.QMessageBox.critical(
            None,
            "Error",
            f"ffmpeg installation failed:\n{e}\n\nPlease install ffmpeg manually from https://ffmpeg.org/download.html.",
        )
        sys.exit(0)


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
    elif speed >= 2:
        concurrent_fragments = "5"
        http_chunk_size = "2097152"
    else:
        concurrent_fragments = "3"
        http_chunk_size = "1048576"
    config["DownloadOptions"] = {
        "concurrent_fragment_downloads": concurrent_fragments,
        "http_chunk_size": http_chunk_size,
        "download_folder": os.path.expanduser("~"),
    }
    with open(CONFIG_FILE, "w") as configfile:
        config.write(configfile)
    return config


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
<<<<<<< Updated upstream
        patterns = ['*.part', '*.part.*', '*.part.tmp', '*.tmp', '*.ytdl']
=======
        patterns = ["*.part", "*.part.*", "*.part.tmp", "*.tmp"]
>>>>>>> Stashed changes
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
