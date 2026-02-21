#!/usr/bin/env python3
"""
MetadataWorker and DownloadWorker
- Adds a small ytdlp logger that prints postprocessor messages to terminal.
- Exports build_ydl_opts(...) so other modules (CLI) can reuse the same option-building logic.
- DownloadWorker supports an optional forced_outtmpl path (full path to output file).
"""

import os
import shutil
import sys
import time

import requests
import yt_dlp
from PyQt6 import QtCore, QtGui
from utils import get_videasy_headers, sanitize_filename


class YTDLPLogger:
    def __init__(self):
        self._last_was_progress = False

    def _is_progress(self, msg: str) -> bool:
        if not msg:
            return False
        s = msg.strip()
        return ("\r" in msg) or (
            s.startswith("[download]") and ("%" in s or "ETA" in s or "of" in s)
        )

    def _finish_progress_line(self):
        if self._last_was_progress:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._last_was_progress = False

    def debug(self, msg):
        if not msg:
            return
        if self._is_progress(msg):
            parts = [p for p in msg.split("\r") if p != ""]
            current = parts[-1] if parts else msg
            # ensure we don't output a trailing newline — use '\r' to overwrite same line
            out = current.rstrip("\n")
            if not out.endswith("\r"):
                out = out + "\r"
            sys.stdout.write(out)
            sys.stdout.flush()
            self._last_was_progress = True
        else:
            self._finish_progress_line()
            if msg.startswith("["):
                print(msg)
            else:
                print(f"[yt-dlp DEBUG] {msg}")

    def info(self, msg):
        if not msg:
            return
        self._finish_progress_line()
        if msg.startswith("["):
            print(msg)
        else:
            print(f"[yt-dlp] {msg}")

    def warning(self, msg):
        if not msg:
            return
        self._finish_progress_line()
        if msg.startswith("["):
            print(msg)
        else:
            print(f"[yt-dlp WARNING] {msg}")

    def error(self, msg):
        if not msg:
            return
        self._finish_progress_line()
        if msg.startswith("["):
            print(msg)
        else:
            print(f"[yt-dlp ERROR] {msg}")


def build_ydl_opts(fmt, video_quality, audio_bitrate, net_config):
    """
    Stateless builder for yt-dlp options that mirrors DownloadWorker._build_base_opts logic.
    Returned dict intentionally does not set 'progress_hooks' (caller attaches it) but does set
    format/merge/postprocessor options.
    """
    ydl_opts = {
        "abort_on_error": False,
        "concurrent_fragment_downloads": int(
            net_config.get("concurrent_fragment_downloads", "3")
        ),
        "http_chunk_size": int(net_config.get("http_chunk_size", "1048576")),
        #  HLS stability
        "retries": 100,
        "fragment_retries": 100,
        "retry_sleep_functions": {
            "fragment": lambda n: 3,
            "http": lambda n: 3,
        },
        "socket_timeout": 10,
        "file_access_retries": 50,
        "downloader": "ffmpeg",
        "hls_use_mpegts": True,
        "continuedl": True,
        "noplaylist": True,
        "cachedir": False,
        "logger": None,
        "remote_components": ["ejs:github"],
    }

    if fmt in ["mp4 (with Audio)", "avi", "mkv"]:
        if video_quality == "best":
            ydl_opts["format"] = "bestvideo+bestaudio/best"
        else:
            if video_quality:
                ydl_opts["format"] = (
                    f"bestvideo[height<={video_quality}]+bestaudio/best[height<={video_quality}]"
                )
            else:
                ydl_opts["format"] = "bestvideo+bestaudio/best"
        if fmt == "mp4 (with Audio)":
            ydl_opts["merge_output_format"] = "mp4"
            ydl_opts["postprocessor_args"] = ["-c", "copy"]
        else:
            ydl_opts["merge_output_format"] = fmt.split()[0].lower()
    elif fmt == "mp4 (without Audio)":
        if video_quality == "best":
            ydl_opts["format"] = "bestvideo"
        else:
            if video_quality:
                ydl_opts["format"] = f"bestvideo[height<={video_quality}]"
            else:
                ydl_opts["format"] = "bestvideo"
        ydl_opts["merge_output_format"] = "mp4"
        ydl_opts["postprocessor_args"] = ["-c", "copy"]
    elif fmt == "mp3":
        ydl_opts["format"] = "bestaudio"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_bitrate,
            }
        ]
    else:
        ydl_opts["format"] = "bestvideo+bestaudio/best"
        ydl_opts["merge_output_format"] = "mp4"
        ydl_opts["postprocessor_args"] = ["-c", "copy"]
    return ydl_opts


def _ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def _is_direct_download_url(url):
    """Return True for URLs that serve a file directly (e.g. SharePoint download links)
    where yt-dlp cannot determine a sensible file extension from the URL path."""
    import urllib.parse

    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    direct_patterns = ["download.aspx", "/_layouts/15/download"]
    return any(p in path for p in direct_patterns)


def _parse_ffmpeg_duration(stderr_line):
    """Extract total duration in seconds from an ffmpeg Duration line.
    Returns float seconds or None."""
    import re

    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr_line)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h * 3600 + mi * 60 + s
    return None


def _parse_ffmpeg_progress(stderr_line):
    """Extract (elapsed_seconds, size_kb) from an ffmpeg progress line.
    Returns (float, int) or (None, None)."""
    import re

    time_m = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", stderr_line)
    size_m = re.search(r"size=\s*(\d+)kB", stderr_line)
    if time_m:
        h, mi, s = int(time_m.group(1)), int(time_m.group(2)), float(time_m.group(3))
        elapsed = h * 3600 + mi * 60 + s
        size_kb = int(size_m.group(1)) if size_m else 0
        return elapsed, size_kb
    return None, None


def _download_direct(url, folder, progress_cb=None, size_cb=None, cancelled_cb=None):
    """Download a direct-serving URL (e.g. SharePoint) by streaming via ffmpeg.

    yt-dlp cannot handle these because the URL path ends with .aspx rather than a video
    extension, causing its internal safety check to abort.  We bypass yt-dlp entirely:
      1. HEAD the URL to get the Content-Disposition filename (if available).
      2. Run ffmpeg -i <url> -c copy output.mp4, parsing stderr for progress updates.

    progress_cb(percent: float, status: str) — called on every ffmpeg progress line
    size_cb(size_str: str)                   — called with human-readable download size
    Returns the output path on success, raises on failure.
    """
    import re
    import subprocess
    import urllib.parse

    # --- resolve final URL (follow redirects with HEAD) ---
    head = requests.head(url, allow_redirects=True, timeout=15)
    final_url = head.url

    # --- determine output filename ---
    cd = head.headers.get("Content-Disposition", "")
    match = re.search(
        r'filename[^;=\n]*=(["\'])?([^;\n]*?)\1(?:;|$)', cd, re.IGNORECASE
    )
    if match:
        raw_name = match.group(2).strip()
        base = os.path.splitext(raw_name)[0]
    else:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(final_url).query)
        token = qs.get("share", ["video"])[0]
        base = sanitize_filename(token) or "video"

    out_path = os.path.join(folder, f"{base}.mp4")
    counter = 1
    while os.path.exists(out_path):
        out_path = os.path.join(folder, f"{base}_{counter}.mp4")
        counter += 1

    print(f"[direct-dl] Saving to: {out_path}")

    # --- run ffmpeg, read stderr for progress ---
    cmd = [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y",
        "-i",
        final_url,
        "-c",
        "copy",
        out_path,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1,
    )

    total_secs = None  # filled once we see the Duration line

    for raw_line in proc.stderr:
        line = raw_line.rstrip()
        if not line:
            continue
        print(f"[ffmpeg] {line}")

        if cancelled_cb and cancelled_cb():
            proc.terminate()
            raise Exception("Cancelled")

        # Try to get total duration from the input info block
        if total_secs is None:
            total_secs = _parse_ffmpeg_duration(line)

        # Parse progress lines (contain "time=" and "size=")
        elapsed, size_kb = _parse_ffmpeg_progress(line)
        if elapsed is not None and progress_cb:
            if total_secs and total_secs > 0:
                percent = min(elapsed / total_secs * 100.0, 99.9)
            else:
                percent = -1  # unknown total; UI should show indeterminate

            # Build a human-readable size string
            size_mb = size_kb / 1024.0
            if size_mb >= 1024:
                size_str = f"{size_mb / 1024:.2f} GB"
            else:
                size_str = f"{size_mb:.1f} MB"

            status = f"Downloading ({size_str})"
            progress_cb(max(percent, 0), status)
            if size_cb:
                size_cb(size_str)

    proc.wait()
    if proc.returncode != 0:
        raise Exception(f"ffmpeg exited with code {proc.returncode}")
    if progress_cb:
        progress_cb(100.0, "Finished")
    return out_path


class MetadataWorker(QtCore.QThread):
    metadata_signal = QtCore.pyqtSignal(dict)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        # Base Options
        ydl_opts = {
            "skip_download": True,
            "extract_flat": True,
            "force_generic_extractor": True,
            "cachedir": False,
            "logger": YTDLPLogger(),
        }

        def _extract(opts):
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(self.url, download=False, process=False)

        try:
            info = _extract(ydl_opts)
        except Exception as e:
            err_str = str(e).lower()
            # on forbidden/403 -> try again with Videasy-Headers
            if "403" in err_str or "forbidden" in err_str:
                try:
                    ydl_opts_with_headers = dict(ydl_opts)
                    ydl_opts_with_headers["http_headers"] = get_videasy_headers()
                    info = _extract(ydl_opts_with_headers)
                except Exception as e2:
                    self.error_signal.emit(str(e2))
                    return
            else:
                self.error_signal.emit(str(e))
                return

        title = info.get("title", "")
        thumb_url = info.get("thumbnail", "")
        filesize = info.get("filesize") or info.get("filesize_approx")
        if filesize:
            size = filesize
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024:
                    filesize_str = f"{size:.2f} {unit}"
                    break
                size /= 1024
            else:
                filesize_str = f"{size:.2f} TB"
        else:
            filesize_str = "Unknown"
        pixmap = None
        if thumb_url:
            try:
                response = requests.get(thumb_url, timeout=1.2)
                image_data = response.content
                image = QtGui.QImage()
                image.loadFromData(image_data)
                pixmap = QtGui.QPixmap.fromImage(image)
            except Exception:
                pixmap = None
        self.metadata_signal.emit(
            {"title": title, "thumbnail": pixmap, "filesize": filesize_str}
        )


class DownloadWorker(QtCore.QThread):
    progress_signal = QtCore.pyqtSignal(float, str)
    finished_signal = QtCore.pyqtSignal()
    error_signal = QtCore.pyqtSignal(str)
    title_signal = QtCore.pyqtSignal(str)
    size_signal = QtCore.pyqtSignal(str)

    def __init__(
        self,
        url,
        folder,
        fmt,
        video_quality,
        audio_bitrate,
        net_config,
        cached_metadata=None,
        forced_outtmpl=None,
        parent=None,
    ):
        super().__init__(parent)
        self.url = url
        self.folder = folder
        self.fmt = fmt
        self.video_quality = video_quality
        self.audio_bitrate = audio_bitrate
        self.net_config = net_config
        self.cached_metadata = cached_metadata
        self.forced_outtmpl = forced_outtmpl  # full path to use as outtmpl if provided
        self._paused = False
        self._cancelled = False
        self.current_outtmpl = None
        self._used_videasy_headers = False

    def progress_hook(self, d):
        if self._cancelled:
            raise Exception("Cancelled")
        while self._paused:
            time.sleep(0.2)
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total * 100) if total else 0
            self.progress_signal.emit(percent, "Downloading")
        elif d.get("status") == "finished":
            self.progress_signal.emit(100, "Finished")

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True

    def _build_base_opts(self):
        ydl_opts = build_ydl_opts(
            self.fmt, self.video_quality, self.audio_bitrate, self.net_config
        )
        ydl_opts["progress_hooks"] = [self.progress_hook]
        ydl_opts["logger"] = YTDLPLogger()
        return ydl_opts

    def _log_available_formats(self, info):
        # Debug helper: print brief overview of available formats to help diagnosing "only audio" issues
        try:
            fmts = info.get("formats") or []
            print("---- available formats (id, ext, vcodec, acodec, filesize) ----")
            for f in fmts:
                print(
                    f"{f.get('format_id')} | {f.get('ext')} | v:{f.get('vcodec')} a:{f.get('acodec')} size:{f.get('filesize') or f.get('filesize_approx')}"
                )
            print("-------------------------------------------------------------")
        except Exception:
            pass

    def run(self):
        # --- SharePoint / direct-download bypass ---
        # yt-dlp cannot handle URLs whose path ends with .aspx because its internal
        # safety check rejects the "unusual extension", even when the server sends a
        # proper video file.  We detect these URLs early and stream them straight
        # through ffmpeg, completely bypassing yt-dlp.
        if _is_direct_download_url(self.url):
            try:
                out = _download_direct(
                    self.url,
                    self.folder,
                    progress_cb=self.progress_signal.emit,
                    size_cb=self.size_signal.emit,
                    cancelled_cb=lambda: self._cancelled,
                )
                self.title_signal.emit(os.path.basename(out))
                self.finished_signal.emit()
            except Exception as e:
                self.error_signal.emit(str(e))
            return  # done – skip all yt-dlp logic below

        ydl_opts = self._build_base_opts()

        # If forced_outtmpl is provided, use it directly
        if self.forced_outtmpl:
            ydl_opts["outtmpl"] = self.forced_outtmpl
            self.current_outtmpl = self.forced_outtmpl
            # If forced_outtmpl lacks an extension we keep ext detection to fallback later;
            # but assume user provided the intended filename.
        # Otherwise fall back to metadata/title-based outtmpl later

        metadata = None
        if self.cached_metadata:
            metadata = self.cached_metadata
            title = metadata.get("title", self.url)
            if not self.forced_outtmpl:
                ext = "mp4"
                safe_title = sanitize_filename(title)
                ydl_opts["outtmpl"] = os.path.join(self.folder, f"{safe_title}.%(ext)s")
                self.current_outtmpl = os.path.join(self.folder, f"{safe_title}.{ext}")
            self.title_signal.emit(title)
            filesize_str = metadata.get("filesize", "Unknown")
            self.size_signal.emit(filesize_str)
        else:
            # Need to extract info (try without special header, retry with headers on 403)
            try:
                if "outtmpl" not in ydl_opts:
                    ydl_opts["outtmpl"] = os.path.join(self.folder, "%(title)s.%(ext)s")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.url, download=False)
                # Log available formats to help debugging
                self._log_available_formats(info)

                # If no video formats are present, try again with videasy headers (if not tried yet)
                formats = info.get("formats") or []
                has_video = any(
                    (f.get("vcodec") and f.get("vcodec") != "none") for f in formats
                )
                if not has_video and not self._used_videasy_headers:
                    try:
                        ydl_opts_with_headers = dict(ydl_opts)
                        ydl_opts_with_headers["http_headers"] = get_videasy_headers()
                        with yt_dlp.YoutubeDL(ydl_opts_with_headers) as ydl:
                            info2 = ydl.extract_info(self.url, download=False)
                        info = info2
                        self._used_videasy_headers = True
                        self._log_available_formats(info)
                        formats = info.get("formats") or []
                        has_video = any(
                            (f.get("vcodec") and f.get("vcodec") != "none")
                            for f in formats
                        )
                        if has_video:
                            ydl_opts = ydl_opts_with_headers
                    except Exception:
                        # ignore here; we'll handle lack of video downstream
                        pass

                title = info.get("title", self.url)
                self.title_signal.emit(title)
                ext = info.get("ext", "mp4")
                if not self.forced_outtmpl:
                    safe_title = sanitize_filename(title)
                    self.current_outtmpl = os.path.join(
                        self.folder, f"{safe_title}.{ext}"
                    )
                    ydl_opts["outtmpl"] = os.path.join(
                        self.folder, f"{safe_title}.%(ext)s"
                    )
                else:
                    # forced_outtmpl already set above
                    pass

                # If no video streams found at all, fall back to downloading the 'best' single-file format (if available)
                if not has_video:
                    print(
                        "[debug] No video codecs detected in formats -> falling back to 'best' single-file format (if available)."
                    )
                    ydl_opts["format"] = "best"
                    # remove merge options because we're downloading single file
                    ydl_opts.pop("merge_output_format", None)
                    ydl_opts.pop("postprocessor_args", None)

                filesize = info.get("filesize") or info.get("filesize_approx")
                if filesize:
                    size = filesize
                    for unit in ["B", "KB", "MB", "GB"]:
                        if size < 1024:
                            filesize_str = f"{size:.2f} {unit}"
                            break
                        size /= 1024
                    else:
                        filesize_str = f"{size:.2f} TB"
                else:
                    filesize_str = "Unknown"
                self.size_signal.emit(filesize_str)
            except Exception as e:
                err_str = str(e).lower()
                # On 403/forbidden -> retry with Videasy-Headers
                if "403" in err_str or "forbidden" in err_str:
                    try:
                        ydl_opts_with_headers = dict(ydl_opts)
                        ydl_opts_with_headers["http_headers"] = get_videasy_headers()
                        with yt_dlp.YoutubeDL(ydl_opts_with_headers) as ydl:
                            info = ydl.extract_info(self.url, download=False)
                        self._used_videasy_headers = True
                        # Log formats and set outtmpl as above
                        self._log_available_formats(info)
                        title = info.get("title", self.url)
                        self.title_signal.emit(title)
                        ext = info.get("ext", "mp4")
                        if not self.forced_outtmpl:
                            safe_title = sanitize_filename(title)
                            self.current_outtmpl = os.path.join(
                                self.folder, f"{safe_title}.{ext}"
                            )
                            ydl_opts = ydl_opts_with_headers
                            ydl_opts["outtmpl"] = os.path.join(
                                self.folder, f"{safe_title}.%(ext)s"
                            )
                        else:
                            ydl_opts = ydl_opts_with_headers
                        filesize = info.get("filesize") or info.get("filesize_approx")
                        if filesize:
                            size = filesize
                            for unit in ["B", "KB", "MB", "GB"]:
                                if size < 1024:
                                    filesize_str = f"{size:.2f} {unit}"
                                    break
                                size /= 1024
                            else:
                                filesize_str = f"{size:.2f} TB"
                        else:
                            filesize_str = "Unknown"
                        # Additional check: if still no video, fall back to 'best'
                        formats = info.get("formats") or []
                        has_video = any(
                            (f.get("vcodec") and f.get("vcodec") != "none")
                            for f in formats
                        )
                        if not has_video:
                            print(
                                "[debug] After headers: still no video detected -> falling back to 'best' format"
                            )
                            ydl_opts["format"] = "best"
                            ydl_opts.pop("merge_output_format", None)
                            ydl_opts.pop("postprocessor_args", None)
                        self.size_signal.emit(filesize_str)
                    except Exception as e2:
                        self.error_signal.emit(str(e2))
                        return
                else:
                    self.error_signal.emit(str(e))
                    return

        # Now perform download (with possible retry on 403 during download)
        # DEBUG: print chosen format and whether ffmpeg is available
        print("[debug] Final ydl_opts format=", ydl_opts.get("format"))
        print("[debug] ffmpeg available=", _ffmpeg_available())

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished_signal.emit()
        except Exception as e:
            err_str = str(e).lower()
            # If we haven't yet used videasy headers and encounter 403, retry once with headers
            if (not self._used_videasy_headers) and (
                "403" in err_str or "forbidden" in err_str
            ):
                try:
                    ydl_opts_with_headers = dict(ydl_opts)
                    ydl_opts_with_headers["http_headers"] = get_videasy_headers()
                    with yt_dlp.YoutubeDL(ydl_opts_with_headers) as ydl:
                        ydl.download([self.url])
                    self.finished_signal.emit()
                    return
                except Exception as e2:
                    e = e2  # fallthrough to error handling below

            # cleanup partially downloaded files
            if self.current_outtmpl:
                for fname in [self.current_outtmpl, self.current_outtmpl + ".part"]:
                    if os.path.exists(fname):
                        try:
                            os.remove(fname)
                        except Exception:
                            pass
            self.error_signal.emit(str(e))
