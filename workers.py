#!/usr/bin/env python3
"""
MetadataWorker and DownloadWorker
- Adds a small ytdlp logger that prints postprocessor messages to terminal.
- DownloadWorker supports an optional forced_outtmpl path (full path to output file).
"""
import os
import time
import yt_dlp
import requests
from PyQt6 import QtCore, QtGui
from utils import get_videasy_headers, sanitize_filename

# Small logger for yt-dlp to forward messages (incl. postprocessor/ffmpeg messages) to terminal.
class YTDLPLogger:
    def debug(self, msg):
        pass

    def info(self, msg):
        if not msg:
            return
        print(f"[yt-dlp] {msg}")

    def warning(self, msg):
        if msg:
            print(f"[yt-dlp WARNING] {msg}")

    def error(self, msg):
        if msg:
            print(f"[yt-dlp ERROR] {msg}")

class MetadataWorker(QtCore.QThread):
    metadata_signal = QtCore.pyqtSignal(dict)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        # Base Options
        ydl_opts = {
            'skip_download': True,
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
            'force_generic_extractor': True,
            'cachedir': False,

            'logger': YTDLPLogger(),
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

        title = info.get('title', '')
        thumb_url = info.get('thumbnail', '')
        filesize = info.get('filesize') or info.get('filesize_approx')
        if filesize:
            size = filesize
            for unit in ['B', 'KB', 'MB', 'GB']:
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
        self.metadata_signal.emit({
            "title": title,
            "thumbnail": pixmap,
            "filesize": filesize_str
        })


class DownloadWorker(QtCore.QThread):
    progress_signal = QtCore.pyqtSignal(float, str)
    finished_signal = QtCore.pyqtSignal()
    error_signal = QtCore.pyqtSignal(str)
    title_signal = QtCore.pyqtSignal(str)
    size_signal = QtCore.pyqtSignal(str)

    def __init__(self, url, folder, fmt, video_quality, audio_bitrate, net_config, cached_metadata=None, forced_outtmpl=None, parent=None):
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
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100) if total else 0
            self.progress_signal.emit(percent, "Downloading")
        elif d.get('status') == 'finished':
            self.progress_signal.emit(100, "Finished")

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True

    def _build_base_opts(self):
        ydl_opts = {
            # default outtmpl will be set/overridden later
            'progress_hooks': [self.progress_hook],
            'abort_on_error': True,
            'concurrent_fragment_downloads': int(self.net_config.get("concurrent_fragment_downloads", "5")),
            'http_chunk_size': int(self.net_config.get("http_chunk_size", "2097152")),
            'noplaylist': True,
            'logger': YTDLPLogger(),
        }
        # Format/merge options
        if self.fmt in ["mp4 (with Audio)", "avi", "mkv"]:
            if self.video_quality == "best":
                ydl_opts['format'] = "bestvideo+bestaudio/best"
            else:
                ydl_opts['format'] = f"bestvideo[height<={self.video_quality}]+bestaudio/best[height<={self.video_quality}]"
            if self.fmt == "mp4 (with Audio)":
                ydl_opts['merge_output_format'] = "mp4"
                ydl_opts['postprocessor_args'] = ['-c', 'copy']
            else:
                ydl_opts['merge_output_format'] = self.fmt.split()[0].lower()
        elif self.fmt == "mp4 (without Audio)":
            if self.video_quality == "best":
                ydl_opts['format'] = "bestvideo"
            else:
                ydl_opts['format'] = f"bestvideo[height<={self.video_quality}]"
            ydl_opts['merge_output_format'] = "mp4"
            ydl_opts['postprocessor_args'] = ['-c', 'copy']
        elif self.fmt == "mp3":
            ydl_opts['format'] = "bestaudio"
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': self.audio_bitrate,
            }]
        else:
            ydl_opts['format'] = "bestvideo+bestaudio/best"
            ydl_opts['merge_output_format'] = "mp4"
            ydl_opts['postprocessor_args'] = ['-c', 'copy']
        return ydl_opts

    def run(self):
        ydl_opts = self._build_base_opts()

        # If forced_outtmpl is provided, use it directly
        if self.forced_outtmpl:
            ydl_opts['outtmpl'] = self.forced_outtmpl
            self.current_outtmpl = self.forced_outtmpl
            # If forced_outtmpl lacks an extension we keep ext detection to fallback later;
            # but assume user provided the intended filename.
        # Otherwise fall back to metadata/title-based outtmpl later

        metadata = None
        if self.cached_metadata:
            metadata = self.cached_metadata
            title = metadata.get('title', self.url)
            if not self.forced_outtmpl:
                ext = "mp4"
                safe_title = sanitize_filename(title)
                ydl_opts['outtmpl'] = os.path.join(self.folder, f"{safe_title}.%(ext)s")
                self.current_outtmpl = os.path.join(self.folder, f"{safe_title}.{ext}")
            self.title_signal.emit(title)
            filesize_str = metadata.get('filesize', "Unknown")
            self.size_signal.emit(filesize_str)
        else:
            # Need to extract info (try without special header, retry with headers on 403)
            try:
                if 'outtmpl' not in ydl_opts:
                    ydl_opts['outtmpl'] = os.path.join(self.folder, '%(title)s.%(ext)s')
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.url, download=False)
                title = info.get('title', self.url)
                self.title_signal.emit(title)
                ext = info.get('ext', 'mp4')
                if not self.forced_outtmpl:
                    safe_title = sanitize_filename(title)
                    self.current_outtmpl = os.path.join(self.folder, f"{safe_title}.{ext}")
                    ydl_opts['outtmpl'] = os.path.join(self.folder, f"{safe_title}.%(ext)s")
                else:
                    # forced_outtmpl already set above
                    pass
                filesize = info.get('filesize') or info.get('filesize_approx')
                if filesize:
                    size = filesize
                    for unit in ['B', 'KB', 'MB', 'GB']:
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
                        title = info.get('title', self.url)
                        self.title_signal.emit(title)
                        ext = info.get('ext', 'mp4')
                        if not self.forced_outtmpl:
                            safe_title = sanitize_filename(title)
                            self.current_outtmpl = os.path.join(self.folder, f"{safe_title}.{ext}")
                            ydl_opts = ydl_opts_with_headers
                            ydl_opts['outtmpl'] = os.path.join(self.folder, f"{safe_title}.%(ext)s")
                        else:
                            # forced_outtmpl already set
                            ydl_opts = ydl_opts_with_headers
                        filesize = info.get('filesize') or info.get('filesize_approx')
                        if filesize:
                            size = filesize
                            for unit in ['B', 'KB', 'MB', 'GB']:
                                if size < 1024:
                                    filesize_str = f"{size:.2f} {unit}"
                                    break
                                size /= 1024
                            else:
                                filesize_str = f"{size:.2f} TB"
                        else:
                            filesize_str = "Unknown"
                        self.size_signal.emit(filesize_str)
                    except Exception as e2:
                        self.error_signal.emit(str(e2))
                        return
                else:
                    self.error_signal.emit(str(e))
                    return

        # Now perform download (with possible retry on 403 during download)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished_signal.emit()
        except Exception as e:
            err_str = str(e).lower()
            # If we haven't yet used videasy headers and encounter 403, retry once with headers
            if (not self._used_videasy_headers) and ("403" in err_str or "forbidden" in err_str):
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
