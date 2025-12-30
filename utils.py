#!/usr/bin/env python3
"""
Helper Functions: ffmpeg-check/install, network speed test, config,
Videasy-Header builder and cleanup helper.
"""
import os
import subprocess
import sys
import platform
import shutil
import time
import configparser
import requests
import glob
from PyQt5 import QtWidgets

CONFIG_FILE = "download_config.ini"
TEST_URL = "https://ipv4.download.thinkbroadband.com/1MB.zip"  # 1MB test file for speed test

def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        QtWidgets.QMessageBox.warning(None, "ffmpeg required",
                                      "This program requires ffmpeg to merge file formats.")
        return False

def install_ffmpeg():
    os_name = platform.system().lower()
    installed = False
    error_msg = ""

    try:
        if os_name == "windows":
            # Try winget first
            if shutil.which("winget"):
                subprocess.run(["winget", "install", "Gyan.FFmpeg.Essentials", "-e", "--silent"], check=True)
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
                subprocess.run(["sudo", "pacman", "-Sy", "ffmpeg", "--noconfirm"], check=True)
                installed = True
            else:
                error_msg = (
                    "No supported package manager found. Please install ffmpeg using your distribution's package manager, "
                    "or download from https://ffmpeg.org/download.html."
                )
        else:
            error_msg = (
                f"Unsupported OS: {os_name}. Please install ffmpeg from https://ffmpeg.org/download.html."
            )

        if installed:
            QtWidgets.QMessageBox.information(
                None, "Success",
                "ffmpeg was successfully installed. Please restart the program."
            )
        else:
            QtWidgets.QMessageBox.critical(
                None, "Error",
                error_msg
            )
            sys.exit(1)
    except Exception as e:
        QtWidgets.QMessageBox.critical(
            None, "Error",
            f"ffmpeg installation failed:\n{e}\n\nPlease install ffmpeg manually from https://ffmpeg.org/download.html."
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
    elif speed >= 2:
        concurrent_fragments = "5"
        http_chunk_size = "2097152"
    else:
        concurrent_fragments = "3"
        http_chunk_size = "1048576"
    config["DownloadOptions"] = {
        "concurrent_fragment_downloads": concurrent_fragments,
        "http_chunk_size": http_chunk_size,
        "download_folder": os.path.expanduser("~")
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
        "Referer": "https://player.videasy.net/"
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
        patterns = ['*.part', '*.part.*', '*.part.tmp', '*.tmp']
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
