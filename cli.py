#!/usr/bin/env python3
from typing import List, Optional
import argparse
import shlex
import sys
import os

import yt_dlp

from utils import load_or_create_config, sanitize_filename, unique_filename, get_videasy_headers
from workers import build_ydl_opts, YTDLPLogger

RESOLUTIONS = ["best", "1080", "720", "480", "360"]
BITRATES = ["320", "256", "192", "128"]
FORMATS = ["mp4 (with Audio)", "mp4 (without Audio)", "mp3", "avi", "mkv"]

def parse_ytdlp_args(arg_list: Optional[List[str]]) -> List[str]:
    if not arg_list:
        return []
    if len(arg_list) > 1:
        return arg_list
    try:
        return shlex.split(arg_list[0])
    except Exception:
        return [arg_list[0]]

def ask_choice(prompt: str, choices: List[str]) -> Optional[str]:
    while True:
        print(prompt)
        for i, c in enumerate(choices, start=1):
            print(f"  {i}) {c}")
        print("  Enter = skip (None)")
        s = input("Choice (number): ").strip()
        if s == "":
            return None
        if not s.isdigit():
            print("Invalid input — please enter a number.")
            continue
        idx = int(s) - 1
        if idx < 0 or idx >= len(choices):
            print("Number out of range.")
            continue
        return choices[idx]

def progress_hook(d):
    status = d.get('status')
    if status == 'downloading':
        downloaded = d.get('downloaded_bytes', 0)
        total = d.get('total_bytes') or d.get('total_bytes_estimate')
        if total:
            pct = downloaded / total * 100
            sys.stdout.write(f"\rDownloading: {pct:.2f}% ({downloaded}/{total} bytes)")
        else:
            sys.stdout.write(f"\rDownloading: {downloaded} bytes")
        sys.stdout.flush()
    elif status == 'finished':
        print("\nDownload finished (processing).")
    elif status == 'error':
        print("\nDownload error.", file=sys.stderr)

def run_cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="video-downloader (cli)", description="CLI for video-downloader (reuses workers options)")
    parser.add_argument("--cli", "-c", action="store_true", help="Start in CLI mode (ignored here)")
    parser.add_argument("url", nargs="?", help="Video URL")
    parser.add_argument("--resolution", "-r", help="Video max height (best, 1080, 720, ...)")
    parser.add_argument("--bitrate", "-b", help="Audio bitrate in kbps (320,256,192,128)")
    parser.add_argument("--format", "-f", help="Format (mp4 (with Audio), mp4 (without Audio), mp3, avi, mkv)")
    parser.add_argument("--filename", "-n", help="Optional filename (without extension). If not provided, filename is NOT prompted interactively.")
    parser.add_argument("--folder", "-d", help="Download folder (if omitted, folder from config is used)")
    parser.add_argument("--ytdlp-args", "-a", nargs="*", help="Raw yt-dlp args (single quoted string or multiple args)")
    args = parser.parse_args(argv)

    # Ensure URL
    url = args.url
    if not url:
        url = input("Video URL: ").strip()
    if not url:
        print("No URL provided, aborting.")
        return 2

    config = load_or_create_config()
    net_config = config["DownloadOptions"]
    folder = args.folder or net_config.get("download_folder") or os.path.expanduser("~")

    extra_ytdlp = parse_ytdlp_args(args.ytdlp_args)
    resolution = args.resolution
    bitrate = args.bitrate
    fmt = args.format

    if fmt is None:
        fmt = ask_choice("Select output format:", FORMATS)
    # Ask resolution for formats that contain video
    if resolution is None and fmt != "mp3":
        resolution = ask_choice("Select video resolution (max height):", RESOLUTIONS)
    # Ask bitrate for formats that include audio (mp4 with audio, avi, mkv) and for mp3 as well
    if bitrate is None and fmt != "mp4 (without Audio)":
        bitrate = ask_choice("Select audio bitrate (kbps):", BITRATES)

    default_ext = "mp4"
    if fmt == "mp3":
        default_ext = "mp3"
    elif fmt == "mp4 (without Audio)":
        default_ext = "mp4"
    elif fmt in ["avi", "mkv"]:
        default_ext = fmt.split()[0].lower()

    base_name = args.filename.strip() if args.filename else None
    final_fullpath = None
    if base_name:
        final_fullpath = unique_filename(folder, base_name, default_ext)

    ydl_opts = build_ydl_opts(fmt or "mp4 (with Audio)", resolution, bitrate, net_config)
    ydl_opts['progress_hooks'] = [progress_hook]
    ydl_opts['logger'] = YTDLPLogger()

    # Naive passthrough for -o/--output from extra args
    if extra_ytdlp:
        for i, a in enumerate(extra_ytdlp):
            if a in ("-o", "--output") and i + 1 < len(extra_ytdlp):
                ydl_opts['outtmpl'] = extra_ytdlp[i + 1]

    if final_fullpath:
        ydl_opts['outtmpl'] = final_fullpath
    else:
        ydl_opts.setdefault('outtmpl', os.path.join(folder, '%(title)s.%(ext)s'))

    if fmt == "mp3" and bitrate:
        if 'postprocessors' in ydl_opts and isinstance(ydl_opts['postprocessors'], list) and ydl_opts['postprocessors']:
            ydl_opts['postprocessors'][0]['preferredquality'] = bitrate

    # Print summary
    print("Starting download with options:")
    print(f"  URL: {url}")
    print(f"  Folder: {folder}")
    print(f"  Format: {fmt}")
    print(f"  Resolution: {resolution}")
    print(f"  Bitrate: {bitrate}")
    if final_fullpath:
        print(f"  Forced filename: {final_fullpath}")
    if extra_ytdlp:
        print("  Extra yt-dlp args:", " ".join(extra_ytdlp))

    # Perform download; retry on 403 with Videasy headers
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("\nDownload finished.")
        return 0
    except Exception as e:
        err = str(e).lower()
        if ("403" in err or "forbidden" in err):
            print("\nReceived 403/forbidden — retrying with special Videasy headers...")
            try:
                ydl_opts_with_headers = dict(ydl_opts)
                ydl_opts_with_headers["http_headers"] = get_videasy_headers()
                with yt_dlp.YoutubeDL(ydl_opts_with_headers) as ydl:
                    ydl.download([url])
                print("\nDownload finished (with headers).")
                return 0
            except Exception as e2:
                print("\nDownload failed:", e2)
                return 1
        else:
            print("\nDownload failed:", e)
            return 1

if __name__ == "__main__":
    rc = run_cli()
    sys.exit(rc)
