#!/home/user/venv/bin/python

import os
import subprocess
import sys
import time
import platform
import shutil
import configparser
import requests
import yt_dlp
from Cryptodome.Cipher import AES
from PyQt5 import QtCore, QtGui, QtWidgets

CONFIG_FILE = "download_config.ini"
TEST_URL = "https://ipv4.download.thinkbroadband.com/1MB.zip"  # 1MB test file for speed test

# -------------------------------
# ffmpeg Check and Installation
# -------------------------------
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
# ------------------------------------------
# Network Speed Test and Config Management
# ------------------------------------------
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

config = load_or_create_config()

# -------------------------------
# Metadata Worker (QThread)
# -------------------------------
class MetadataWorker(QtCore.QThread):
    metadata_signal = QtCore.pyqtSignal(dict)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        # Minimal options for fast metadata extraction
        ydl_opts = {
            'skip_download': True,
            'extract_flat': True,  # Nur grundlegende Informationen abrufen
            'quiet': True,
            'no_warnings': True,
            'force_generic_extractor': True,
            'cachedir': False
        }
        if "workers" in self.url:
            ydl_opts["http_headers"] = {
                "User-Agent": "Mozilla/5.0",
                "Origin": "https://player.videasy.net",
                "Referer": "https://player.videasy.net/"
            }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False, process=False)
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
                    # Timeout auf 1.2 Sekunden reduziert
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
        except Exception as e:
            self.error_signal.emit(str(e))

# -------------------------------
# Download Worker (QThread)
# -------------------------------
class DownloadWorker(QtCore.QThread):
    progress_signal = QtCore.pyqtSignal(float, str)
    finished_signal = QtCore.pyqtSignal()
    error_signal = QtCore.pyqtSignal(str)
    title_signal = QtCore.pyqtSignal(str)
    size_signal = QtCore.pyqtSignal(str)

    def __init__(self, url, folder, fmt, video_quality, audio_bitrate, net_config, cached_metadata=None, parent=None):
        super().__init__(parent)
        self.url = url
        self.folder = folder
        self.fmt = fmt
        self.video_quality = video_quality
        self.audio_bitrate = audio_bitrate
        self.net_config = net_config
        self.cached_metadata = cached_metadata
        self._paused = False
        self._cancelled = False
        self.current_outtmpl = None

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

    def run(self):
        ydl_opts = {
            'outtmpl': os.path.join(self.folder, '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'abort_on_error': True,
            'concurrent_fragment_downloads': int(self.net_config.get("concurrent_fragment_downloads", "5")),
            'http_chunk_size': int(self.net_config.get("http_chunk_size", "2097152")),
            'noplaylist': True,
        }
        if "workers" in self.url:
            ydl_opts["http_headers"] = {
                "User-Agent": "Mozilla/5.0",
                "Origin": "https://player.videasy.net",
                "Referer": "https://player.videasy.net/"
            }
            ydl_opts['format'] = "best"

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

        if self.cached_metadata:
            metadata = self.cached_metadata
            title = metadata.get('title', self.url)
            self.title_signal.emit(title)
            ext = "mp4"
            self.current_outtmpl = os.path.join(self.folder, f"{title}.{ext}")
            filesize_str = metadata.get('filesize', "Unknown")
            self.size_signal.emit(filesize_str)
        else:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                title = info.get('title', self.url)
                self.title_signal.emit(title)
                ext = info.get('ext', 'mp4')
                self.current_outtmpl = os.path.join(self.folder, f"{title}.{ext}")
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
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished_signal.emit()
        except Exception as e:
            if self.current_outtmpl:
                for fname in [self.current_outtmpl, self.current_outtmpl + ".part"]:
                    if os.path.exists(fname):
                        try:
                            os.remove(fname)
                        except Exception:
                            pass
            self.error_signal.emit(str(e))

# -------------------------------
# Main Window (PyQt5) – Dark Mode
# -------------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Downloader UI")
        self.resize(900, 750)

        # Cached metadata
        self.cached_url = None
        self.cached_metadata = None
        self.last_url = ""

        # Central widget and layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # Input form
        form_layout = QtWidgets.QFormLayout()
        self.url_edit = QtWidgets.QLineEdit()
        form_layout.addRow("Video URL:", self.url_edit)
        self.url_edit.textChanged.connect(self.on_url_changed)

        folder_layout = QtWidgets.QHBoxLayout()
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_edit.setText(config["DownloadOptions"].get("download_folder", os.path.expanduser("~")))
        folder_button = QtWidgets.QPushButton("Choose Folder")
        folder_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(folder_button)
        form_layout.addRow("Download Folder:", folder_layout)

        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(["mp4 (with Audio)", "mp4 (without Audio)", "mp3", "avi", "mkv"])
        self.format_combo.currentIndexChanged.connect(self.update_quality_ui)
        form_layout.addRow("Format:", self.format_combo)

        # Quality settings
        self.video_quality_combo = QtWidgets.QComboBox()
        self.video_quality_combo.addItems(["best", "1080", "720", "480", "360"])
        self.audio_quality_combo = QtWidgets.QComboBox()
        self.audio_quality_combo.addItems(["320", "256", "192", "128"])

        self.quality_widget = QtWidgets.QWidget()
        quality_layout = QtWidgets.QHBoxLayout(self.quality_widget)
        self.video_group = QtWidgets.QGroupBox("Video Quality (max. Height)")
        v_layout = QtWidgets.QHBoxLayout(self.video_group)
        v_layout.addWidget(self.video_quality_combo)
        self.audio_group = QtWidgets.QGroupBox("Audio Bitrate (kbps)")
        a_layout = QtWidgets.QHBoxLayout(self.audio_group)
        a_layout.addWidget(self.audio_quality_combo)
        quality_layout.addWidget(self.video_group)
        quality_layout.addWidget(self.audio_group)
        form_layout.addRow("Quality Settings:", self.quality_widget)
        self.update_quality_ui()

        main_layout.addLayout(form_layout)

        # Thumbnail and title preview
        self.thumbnail_label = QtWidgets.QLabel()
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_label.setFixedHeight(200)
        self.thumbnail_label.hide()
        main_layout.addWidget(self.thumbnail_label)

        self.preview_title = QtWidgets.QLabel("Title: -")
        main_layout.addWidget(self.preview_title)

        # Download button
        top_action_layout = QtWidgets.QVBoxLayout()
        self.download_button = QtWidgets.QPushButton("Start Download")
        self.download_button.clicked.connect(self.start_download)
        top_action_layout.addWidget(self.download_button)
        main_layout.addLayout(top_action_layout)

        # Overall progress bar
        self.overall_progress_bar = QtWidgets.QProgressBar()
        self.overall_progress_bar.setValue(0)
        main_layout.addWidget(self.overall_progress_bar)

        # Download table
        self.download_table = QtWidgets.QTableWidget(0, 5)
        self.download_table.setHorizontalHeaderLabels(["Title", "Status", "Progress", "Size", "Actions"])
        self.download_table.horizontalHeader().setStretchLastSection(True)
        self.download_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.download_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.download_table.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.download_table)

        self.active_downloads = {}
        self.download_progress = {}

    def on_url_changed(self, text):
        text = text.strip()
        if not text:
            return
        if text != self.last_url:
            self.last_url = text
            self.preview_title.setText("Title: Loading metadata...")
            self.thumbnail_label.setText("Loading thumbnail...")
            self.thumbnail_label.show()
            QtCore.QTimer.singleShot(100, self.load_metadata)

    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose Folder")
        if folder:
            self.folder_edit.setText(folder)
            config["DownloadOptions"]["download_folder"] = folder
            with open(CONFIG_FILE, "w") as configfile:
                config.write(configfile)

    def update_quality_ui(self):
        fmt = self.format_combo.currentText()
        if fmt == "mp3":
            self.video_group.hide()
            self.audio_group.show()
        elif fmt == "mp4 (without Audio)":
            self.video_group.show()
            self.audio_group.hide()
        elif fmt in ["avi", "mkv"]:
            self.video_group.show()
            self.audio_group.show()
        else:
            self.video_group.show()
            self.audio_group.show()

    def load_metadata(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        self.preview_title.setText("Title: Loading metadata...")
        self.thumbnail_label.setText("Loading thumbnail...")
        self.thumbnail_label.show()
        self.metadata_worker = MetadataWorker(url)
        self.metadata_worker.metadata_signal.connect(self.on_metadata_loaded)
        self.metadata_worker.error_signal.connect(lambda e: print("Metadata error:", e))
        self.metadata_worker.start()

    def on_metadata_loaded(self, metadata):
        current_url = self.url_edit.text().strip()
        if current_url != "":
            self.cached_url = current_url
        self.cached_metadata = metadata

        title = metadata.get("title", "")
        self.preview_title.setText(f"Title: {title}")
        pixmap = metadata.get("thumbnail")
        if pixmap:
            scaled = pixmap.scaled(self.thumbnail_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled)
        else:
            self.thumbnail_label.hide()

    def start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QtWidgets.QMessageBox.critical(self, "Error", "Please enter a valid file URL.")
            return
        folder = self.folder_edit.text().strip()
        if not folder:
            QtWidgets.QMessageBox.critical(self, "Error", "Please choose a download folder.")
            return
        fmt = self.format_combo.currentText()
        if fmt == "mp3":
            video_quality = None
            audio_bitrate = self.audio_quality_combo.currentText()
        elif fmt == "mp4 (without Audio)":
            video_quality = self.video_quality_combo.currentText()
            audio_bitrate = None
        else:
            video_quality = self.video_quality_combo.currentText()
            audio_bitrate = self.audio_quality_combo.currentText()

        cached = self.cached_metadata if self.cached_url == url else None
        self.thumbnail_label.hide()
        self.url_edit.clear()

        worker = DownloadWorker(url, folder, fmt, video_quality, audio_bitrate, config["DownloadOptions"], cached_metadata=cached)
        row = self.download_table.rowCount()
        self.download_table.insertRow(row)
        for col, text in enumerate(["Loading metadata...", "Waiting", "0%", "Unknown", "Right click for options"]):
            item = QtWidgets.QTableWidgetItem(text)
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.download_table.setItem(row, col, item)
        self.active_downloads[row] = worker
        self.download_progress[row] = 0

        worker.title_signal.connect(lambda t, r=row: self.download_table.item(r, 0).setText(t))
        worker.progress_signal.connect(lambda p, s, r=row: self.update_download_row(r, p, s))
        worker.size_signal.connect(lambda s, r=row: self.download_table.item(r, 3).setText(s))
        worker.finished_signal.connect(lambda r=row: self.download_finished(r))
        worker.error_signal.connect(lambda err, r=row: self.download_error(r, err))
        worker.start()

    def update_download_row(self, row, progress, status):
        self.download_progress[row] = progress
        self.download_table.item(row, 1).setText(status)
        self.download_table.item(row, 2).setText(f"{progress:.2f}%")
        if "paused" in status.lower():
            color = QtGui.QColor("#F39C12")   # Orange
        elif "cancelled" in status.lower():
            color = QtGui.QColor("#E74C3C")   # Red
        elif "finished" in status.lower():
            color = QtGui.QColor("#2ECC71")   # Green
        elif "waiting" in status.lower():
            color = QtGui.QColor("#F1C40F")   # Light yellow
        elif "downloading" in status.lower():
            color = QtGui.QColor("#3498DB")   # Blue
        else:
            color = QtGui.QColor("#3498DB")
        for col in range(self.download_table.columnCount()):
            self.download_table.item(row, col).setBackground(color)
        self.update_overall_progress()

    def update_overall_progress(self):
        total_progress = 0
        count = 0
        for row in range(self.download_table.rowCount()):
            status = self.download_table.item(row, 1).text().lower()
            if "cancelled" in status:
                continue
            try:
                progress = float(self.download_table.item(row, 2).text().replace("%", ""))
                total_progress += progress
                count += 1
            except:
                pass
        overall = total_progress / count if count > 0 else 0
        self.overall_progress_bar.setValue(int(overall))

    def download_finished(self, row):
        self.download_table.item(row, 1).setText("Finished")
        self.download_progress[row] = 100
        self.update_overall_progress()

    def download_error(self, row, err):
        self.download_table.item(row, 1).setText(f"Error: {err}")
        self.download_progress[row] = 0
        self.update_overall_progress()

    def show_context_menu(self, pos):
        index = self.download_table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        worker = self.active_downloads.get(row)
        if not worker:
            return
        menu = QtWidgets.QMenu()
        if worker._paused:
            pause_action = menu.addAction("Continue")
        else:
            pause_action = menu.addAction("Pause")
        cancel_action = menu.addAction("Cancel")
        action = menu.exec_(self.download_table.viewport().mapToGlobal(pos))
        if action == pause_action:
            if worker._paused:
                worker.resume()
                self.download_table.item(row, 1).setText("Downloading")
            else:
                worker.pause()
                self.download_table.item(row, 1).setText("Paused")
        elif action == cancel_action:
            worker.cancel()
            self.download_table.item(row, 1).setText("Cancelled")
            if worker.current_outtmpl:
                for fname in [worker.current_outtmpl, worker.current_outtmpl + ".part"]:
                    if os.path.exists(fname):
                        try:
                            os.remove(fname)
                        except Exception:
                            pass
            self.update_overall_progress()

def main():
    app = QtWidgets.QApplication(sys.argv)
    if not check_ffmpeg():
        install = QtWidgets.QMessageBox.question(None, "ffmpeg missing",
                                                 "ffmpeg is not installed. Install now?",
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if install == QtWidgets.QMessageBox.Yes:
            install_ffmpeg()
        else:
            sys.exit(1)
    dark_stylesheet = """
        QWidget { background-color: #2E2E2E; color: #FFFFFF; }
        QLineEdit, QComboBox, QPlainTextEdit { background-color: #3E3E3E; color: #FFFFFF; }
        QPushButton { background-color: #3E3E3E; border: none; padding: 5px; }
        QPushButton:hover { background-color: #5E5E5E; }
        QHeaderView::section { background-color: #3E3E3E; color: #FFFFFF; }
        QTableWidget { gridline-color: #95A5A6; }
    """
    app.setStyleSheet(dark_stylesheet)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
