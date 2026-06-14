#!/usr/bin/env python3
import argparse
import os
import shlex
import sys
from typing import List, Optional

import yt_dlp

from utils import (
    get_videasy_headers,
    load_or_create_config,
    unique_filename,
)
from workers import (
    YTDLPLogger,
    _download_direct,
    _is_direct_download_url,
    build_ydl_opts,
)

RESOLUTIONS = ["best", "1080", "720", "480", "360"]
BITRATES = ["320", "256", "192", "128"]
FORMATS = ["mp4 (with Audio)", "mp4 (without Audio)", "mp3", "avi", "mkv"]


class CLILogger(YTDLPLogger):
    def __init__(self):
        super().__init__()
        self.progress_hook_active = False

    def _finish_progress_line(self):
        if self._last_was_progress or self.progress_hook_active:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._last_was_progress = False
            self.progress_hook_active = False


class _AutoFlush:
    """Thin wrapper around a text stream that flushes after every write."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, s):
        result = self._stream.write(s)
        self._stream.flush()
        return result

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def parse_ytdlp_args(arg_list: Optional[List[str]]) -> List[str]:
    if not arg_list:
        return []
    if len(arg_list) > 1:
        return arg_list
    try:
        return shlex.split(arg_list[0])
    except Exception:
        return [arg_list[0]]


def apply_extra_ytdlp_args(ydl_opts: dict, extra_args: List[str]) -> None:
    """
    Parse raw yt-dlp CLI arguments (e.g. ['--cookies', 'cookies.txt',
    '--no-check-certificates']) and merge them into an existing ydl_opts dict.

    Supports:
      --cookies FILE            -> cookiefile
      --cookies-from-browser BR -> cookiesfrombrowser
      --no-check-certificates   -> nocheckcertificate
      --proxy URL               -> proxy
      --geo-bypass              -> geo_bypass
      --user-agent UA           -> user_agent
      --referer REF             -> referer
      --add-header K:V          -> http_headers[K] = V
      --sleep-interval N        -> sleep_interval
      --max-sleep-interval N    -> max_sleep_interval
      --rate-limit RATE         -> ratelimit
      --retries N               -> retries
      --fragment-retries N      -> fragment_retries
      --socket-timeout N        -> socket_timeout
      --source-address IP       -> source_address
      --force-ipv4              -> source_address (0.0.0.0)
      --force-ipv6              -> source_address (::)
      --no-playlist             -> noplaylist = True
      --yes-playlist            -> noplaylist = False
      --playlist-start N        -> playliststart
      --playlist-end N          -> playlistend
      --playlist-items ITEMS    -> playlist_items
      --write-subs              -> writesubtitles
      --sub-langs LANGS         -> subtitleslangs
      --embed-subs              -> embedsubtitles
      --write-thumbnail         -> writethumbnail
      --embed-thumbnail         -> embedthumbnail
      --write-info-json         -> writeinfojson
      --username USER           -> username
      --password PASS           -> password
      --netrc                   -> usenetrc
      --netrc-location PATH     -> netrc_location
      --sponsorblock-remove CAT -> sponsorblock_remove
      --sponsorblock-mark CAT   -> sponsorblock_mark
      -o / --output TMPL        -> outtmpl  (already handled but kept for completeness)
      --verbose / -v            -> verbose
      --quiet / -q              -> quiet

    Unknown args are printed as a warning but do NOT abort the download.
    """
    if not extra_args:
        return

    # Flags that map directly to a bool key (no value argument)
    BOOL_FLAGS: dict = {
        "--no-check-certificates": ("nocheckcertificate", True),
        "--no-check-certificate": ("nocheckcertificate", True),
        "--geo-bypass": ("geo_bypass", True),
        "--no-playlist": ("noplaylist", True),
        "--yes-playlist": ("noplaylist", False),
        "--write-subs": ("writesubtitles", True),
        "--write-sub": ("writesubtitles", True),
        "--embed-subs": ("embedsubtitles", True),
        "--embed-sub": ("embedsubtitles", True),
        "--write-thumbnail": ("writethumbnail", True),
        "--embed-thumbnail": ("embedthumbnail", True),
        "--write-info-json": ("writeinfojson", True),
        "--netrc": ("usenetrc", True),
        "--force-ipv4": ("source_address", "0.0.0.0"),
        "--force-ipv6": ("source_address", "::"),
        "--verbose": ("verbose", True),
        "-v": ("verbose", True),
        "--quiet": ("quiet", True),
        "-q": ("quiet", True),
    }

    # Args that take exactly one value: flag -> ydl_opts key
    VALUE_FLAGS: dict = {
        "--cookies": "cookiefile",
        "--cookies-from-browser": "cookiesfrombrowser",
        "--proxy": "proxy",
        "--user-agent": "user_agent",
        "--referer": "referer",
        "--sleep-interval": "sleep_interval",
        "--max-sleep-interval": "max_sleep_interval",
        "--min-sleep-interval": "sleep_interval",
        "--rate-limit": "ratelimit",
        "--retries": "retries",
        "--fragment-retries": "fragment_retries",
        "--socket-timeout": "socket_timeout",
        "--source-address": "source_address",
        "--playlist-start": "playliststart",
        "--playlist-end": "playlistend",
        "--playlist-items": "playlist_items",
        "--sub-langs": "subtitleslangs",
        "--sub-lang": "subtitleslangs",
        "--username": "username",
        "-u": "username",
        "--password": "password",
        "-p": "password",
        "--netrc-location": "netrc_location",
        "--sponsorblock-remove": "sponsorblock_remove",
        "--sponsorblock-mark": "sponsorblock_mark",
        "-o": "outtmpl",
        "--output": "outtmpl",
    }

    # Integer-cast keys
    INT_KEYS = {
        "sleep_interval",
        "max_sleep_interval",
        "retries",
        "fragment_retries",
        "socket_timeout",
        "playliststart",
        "playlistend",
    }

    i = 0
    while i < len(extra_args):
        arg = extra_args[i]

        if arg in BOOL_FLAGS:
            key, val = BOOL_FLAGS[arg]
            ydl_opts[key] = val
            i += 1
            continue

        if arg in VALUE_FLAGS:
            key = VALUE_FLAGS[arg]
            if i + 1 >= len(extra_args):
                print(f"[yt-dlp-args] Warning: '{arg}' requires a value, ignoring.")
                i += 1
                continue
            val_str = extra_args[i + 1]
            i += 2

            if key == "ratelimit":
                # yt-dlp accepts e.g. "500K", "1M"
                # Try to parse common suffixes
                try:
                    val_str_upper = val_str.upper()
                    if val_str_upper.endswith("K"):
                        ydl_opts[key] = int(float(val_str_upper[:-1]) * 1024)
                    elif val_str_upper.endswith("M"):
                        ydl_opts[key] = int(float(val_str_upper[:-1]) * 1024 * 1024)
                    elif val_str_upper.endswith("G"):
                        ydl_opts[key] = int(float(val_str_upper[:-1]) * 1024**3)
                    else:
                        ydl_opts[key] = int(val_str)
                except ValueError:
                    print(
                        f"[yt-dlp-args] Warning: could not parse rate-limit '{val_str}', ignoring."
                    )
                continue

            if key in INT_KEYS:
                try:
                    ydl_opts[key] = int(val_str)
                except ValueError:
                    print(
                        f"[yt-dlp-args] Warning: expected integer for '{arg}', got '{val_str}', ignoring."
                    )
                continue

            if key == "subtitleslangs":
                # Accept comma-separated list
                ydl_opts[key] = [l.strip() for l in val_str.split(",")]
                continue

            if key == "cookiesfrombrowser":
                # yt-dlp accepts "chrome", "firefox+keychain", etc.
                ydl_opts[key] = (val_str,)
                continue

            if key == "sponsorblock_remove" or key == "sponsorblock_mark":
                ydl_opts[key] = [c.strip() for c in val_str.split(",")]
                continue

            ydl_opts[key] = val_str
            continue

        # --- --add-header KEY:VALUE ---
        if arg == "--add-header":
            if i + 1 >= len(extra_args):
                print(
                    "[yt-dlp-args] Warning: '--add-header' requires a value, ignoring."
                )
                i += 1
                continue
            header_str = extra_args[i + 1]
            i += 2
            if ":" not in header_str:
                print(
                    f"[yt-dlp-args] Warning: '--add-header' value must be 'Key:Value', got '{header_str}', ignoring."
                )
                continue
            hkey, hval = header_str.split(":", 1)
            headers = ydl_opts.setdefault("http_headers", {})
            headers[hkey.strip()] = hval.strip()
            continue

        # --- unknown / unsupported ---
        if arg.startswith("-") and not arg.startswith("--") and len(arg) == 2:
            # single-char flag with value
            print(
                f"[yt-dlp-args] Warning: unsupported arg '{arg}' (and its value), passing through is not supported, ignoring."
            )
            i += 2
            continue
        elif arg.startswith("-"):
            print(f"[yt-dlp-args] Warning: unsupported arg '{arg}', ignoring.")
            i += 1
            continue
        else:
            # positional
            i += 1
            continue


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
            print("Invalid input: please enter a number.")
            continue
        idx = int(s) - 1
        if idx < 0 or idx >= len(choices):
            print("Number out of range.")
            continue
        return choices[idx]


def make_progress_hook(logger: CLILogger):
    def progress_hook(d):
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            speed = d.get("speed")
            eta = d.get("eta")
            speed_str = f"  {speed / 1024:.0f} KB/s" if speed else ""
            eta_str = f"  ETA {eta}s" if eta is not None else ""
            if total:
                pct = downloaded / total * 100
                sys.stdout.write(f"\rDownloading: {pct:.1f}%{speed_str}{eta_str}   ")
            else:
                sys.stdout.write(f"\rDownloading: {downloaded} bytes{speed_str}   ")
            sys.stdout.flush()
            logger.progress_hook_active = True
        elif status == "finished":
            logger.progress_hook_active = False
            logger._last_was_progress = False
            sys.stdout.write("\n")
            print("Download finished, post-processing...")
            sys.stdout.flush()
        elif status == "error":
            logger.progress_hook_active = False
            sys.stdout.write("\n")
            sys.stdout.flush()
            print("Download error.", file=sys.stderr)

    return progress_hook


def run_cli(argv: Optional[List[str]] = None) -> int:
    if not isinstance(sys.stdout, _AutoFlush):
        sys.stdout = _AutoFlush(sys.stdout)
    if not isinstance(sys.stderr, _AutoFlush):
        sys.stderr = _AutoFlush(sys.stderr)

    parser = argparse.ArgumentParser(
        prog="video-downloader (cli)",
        description="CLI for video-downloader (reuses workers options)",
    )
    parser.add_argument(
        "--cli", "-c", action="store_true", help="Start in CLI mode (ignored here)"
    )
    parser.add_argument("url", nargs="?", help="Video URL")
    parser.add_argument(
        "--resolution", "-r", help="Video max height (best, 1080, 720, ...)"
    )
    parser.add_argument(
        "--bitrate", "-b", help="Audio bitrate in kbps (320,256,192,128)"
    )
    parser.add_argument(
        "--format",
        "-f",
        help="Format (mp4 (with Audio), mp4 (without Audio), mp3, avi, mkv)",
    )
    parser.add_argument(
        "--filename",
        "-n",
        help="Optional filename (without extension). If not provided, filename is NOT prompted interactively.",
    )
    parser.add_argument(
        "--folder",
        "-d",
        help="Download folder (if omitted, folder from config is used)",
    )
    parser.add_argument(
        "--ytdlp-args",
        "-a",
        nargs="*",
        help=(
            "Pass raw yt-dlp arguments as a quoted string or space-separated tokens. "
            "Example: --ytdlp-args '--cookies cookies.txt --proxy socks5://127.0.0.1:1080'. "
            "Supported: --cookies, --cookies-from-browser, --proxy, --user-agent, --referer, "
            "--add-header, --no-check-certificates, --geo-bypass, --rate-limit, --retries, "
            "--fragment-retries, --socket-timeout, --force-ipv4, --force-ipv6, "
            "--no-playlist, --yes-playlist, --playlist-start, --playlist-end, --playlist-items, "
            "--write-subs, --sub-langs, --embed-subs, --write-thumbnail, --embed-thumbnail, "
            "--write-info-json, --username, --password, --netrc, --sponsorblock-remove, "
            "-o/--output, --verbose, --quiet."
        ),
    )
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
    deno_path = net_config.get("deno_path", "").strip()

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

    ydl_opts = build_ydl_opts(
        fmt or "mp4 (with Audio)",
        resolution,
        bitrate,
        net_config,
        deno_path=deno_path,
    )
    cli_logger = CLILogger()
    ydl_opts["progress_hooks"] = [make_progress_hook(cli_logger)]
    ydl_opts["logger"] = cli_logger

    # Apply all extra yt-dlp args (--cookies, --proxy, --add-header, -o, ...)
    if extra_ytdlp:
        apply_extra_ytdlp_args(ydl_opts, extra_ytdlp)

    if final_fullpath:
        ydl_opts["outtmpl"] = final_fullpath
    else:
        ydl_opts.setdefault("outtmpl", os.path.join(folder, "%(title)s.%(ext)s"))

    if fmt == "mp3" and bitrate:
        if (
            "postprocessors" in ydl_opts
            and isinstance(ydl_opts["postprocessors"], list)
            and ydl_opts["postprocessors"]
        ):
            ydl_opts["postprocessors"][0]["preferredquality"] = bitrate

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

    # --- SharePoint / direct-download bypass (same as GUI path) ---
    if _is_direct_download_url(url):
        print("  Mode: direct ffmpeg download (SharePoint/aspx URL detected)")

        def cli_progress(percent, status):
            sys.stdout.write(f"\r{status}  {percent:.1f}%   ")
            sys.stdout.flush()

        def cli_size(size_str):
            pass  # already shown inside cli_progress status string

        cancelled = [False]
        try:
            out = _download_direct(
                url,
                folder,
                progress_cb=cli_progress,
                size_cb=cli_size,
                cancelled_cb=lambda: cancelled[0],
            )
            print(f"\nDownload finished: {out}")
            return 0
        except Exception as e:
            print(f"\nDownload failed: {e}")
            return 1

    # Perform download via yt-dlp; retry on 403 with Videasy headers
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("\nDownload finished.")
        return 0
    except Exception as e:
        err = str(e).lower()
        if "403" in err or "forbidden" in err:
            print("\nReceived 403/forbidden, retrying with special Videasy headers...")
            try:
                ydl_opts_with_headers = dict(ydl_opts)
                ydl_opts_with_headers["http_headers"] = get_videasy_headers()
                ydl_opts_with_headers["logger"] = cli_logger
                ydl_opts_with_headers["progress_hooks"] = [
                    make_progress_hook(cli_logger)
                ]
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
