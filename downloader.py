import os
import subprocess
import time
import configparser
import requests
import yt_dlp

from PyQt5 import QtCore, QtGui, QtWidgets

CONFIG_FILE = "download_config.ini"
TEST_URL = "https://ipv4.download.thinkbroadband.com/1MB.zip"  # 1MB-Datei für Speedtest

# -------------------------------
# ffmpeg-Check und Installation
# -------------------------------
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        QtWidgets.QMessageBox.warning(None, "ffmpeg benötigt",
                                      "Dieses Programm benötigt ffmpeg. Bitte installiere es (z. B. via winget).")
        return False

def install_ffmpeg():
    try:
        subprocess.run(["winget", "install", "Gyan.FFmpeg.Essentials", "-e", "--silent"], check=True)
        QtWidgets.QMessageBox.information(None, "Erfolg", "ffmpeg wurde erfolgreich installiert. Bitte starte das Programm neu.")
        sys.exit(app.exec_())
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Fehler", f"ffmpeg-Installation fehlgeschlagen:\n{e}")
        sys.exit(app.exec_())

# ------------------------------------------
# Netzwerk Speed Test und Konfigurationsverwaltung
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
# Download Worker (QThread)
# -------------------------------
class DownloadWorker(QtCore.QThread):
    progress_signal = QtCore.pyqtSignal(float, str)  # Fortschritt in % und Status-Text
    finished_signal = QtCore.pyqtSignal()
    error_signal = QtCore.pyqtSignal(str)
    title_signal = QtCore.pyqtSignal(str)

    def __init__(self, url, folder, fmt, video_quality, audio_bitrate, net_config, parent=None):
        super().__init__(parent)
        self.url = url
        self.folder = folder
        self.fmt = fmt
        self.video_quality = video_quality
        self.audio_bitrate = audio_bitrate
        self.net_config = net_config
        self._paused = False
        self._cancelled = False
        self.current_outtmpl = None  # wird gesetzt, sobald Metadaten bekannt sind

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True

    def progress_hook(self, d):
        if self._cancelled:
            raise Exception("Download abgebrochen vom Benutzer.")
        while self._paused:
            time.sleep(0.2)
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100) if total else 0
            self.progress_signal.emit(percent, f"Lädt... {percent:.2f}%")
        elif d.get('status') == 'finished':
            self.progress_signal.emit(100, "Fertig, verarbeite...")

    def run(self):
        ydl_opts = {
            'outtmpl': os.path.join(self.folder, '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'abort_on_error': True,
            'concurrent_fragment_downloads': int(self.net_config.get("concurrent_fragment_downloads", "5")),
            'http_chunk_size': int(self.net_config.get("http_chunk_size", "2097152")),
            'noplaylist': True,
        }
        # Anpassung je nach Format und einstellbaren Parametern:
        if self.fmt in ["mp4 (mit Audio)", "avi", "mkv"]:
            # Für Formate mit Video und Audio: Beide Parameter werden berücksichtigt.
            if self.video_quality == "best":
                ydl_opts['format'] = "bestvideo+bestaudio/best"
            else:
                ydl_opts['format'] = f"bestvideo[height<={self.video_quality}]+bestaudio/best[height<={self.video_quality}]"
            if self.fmt == "mp4 (mit Audio)":
                ydl_opts['merge_output_format'] = "mp4"
                ydl_opts['postprocessor_args'] = ['-c', 'copy']
            else:
                ydl_opts['merge_output_format'] = self.fmt.split()[0].lower()
        elif self.fmt == "mp4 (ohne Audio)":
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

        try:
            # Zuerst Metadaten abrufen
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                title = info.get('title', self.url)
                self.title_signal.emit(title)
                # Ausgabedatei festlegen
                ext = info.get('ext', 'mp4')
                self.current_outtmpl = os.path.join(self.folder, f"{title}.{ext}")
            # Download starten
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished_signal.emit()
        except Exception as e:
            # Bei Abbruch oder Fehler: Falls Teil-Dateien existieren, löschen
            if self.current_outtmpl:
                part_file = self.current_outtmpl + ".part"
                if os.path.exists(part_file):
                    try:
                        os.remove(part_file)
                    except Exception:
                        pass
            self.error_signal.emit(str(e))

# -------------------------------
# Hauptfenster (PyQt5) – Dark Mode
# -------------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Downloader UI")
        self.resize(900, 700)

        # Zentrales Widget und Layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # Eingabeformular (URL, Ordner, Format und Qualitäts-Parameter)
        form_layout = QtWidgets.QFormLayout()
        self.url_edit = QtWidgets.QLineEdit()
        form_layout.addRow("Video URL:", self.url_edit)

        folder_layout = QtWidgets.QHBoxLayout()
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_edit.setText(config["DownloadOptions"].get("download_folder", os.path.expanduser("~")))
        folder_button = QtWidgets.QPushButton("Ordner wählen")
        folder_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(folder_button)
        form_layout.addRow("Download-Ordner:", folder_layout)

        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(["mp4 (mit Audio)", "mp4 (ohne Audio)", "mp3", "avi", "mkv"])
        self.format_combo.currentIndexChanged.connect(self.update_quality_ui)
        form_layout.addRow("Format:", self.format_combo)

        # Zwei Gruppen für Video- und Audio-Einstellungen
        self.video_quality_combo = QtWidgets.QComboBox()
        self.video_quality_combo.addItems(["best", "1080", "720", "480", "360"])
        self.audio_quality_combo = QtWidgets.QComboBox()
        self.audio_quality_combo.addItems(["320", "256", "192", "128"])

        # Bei "mp4 (mit Audio)" sollen beide Gruppen angezeigt werden:
        self.quality_widget = QtWidgets.QWidget()
        quality_layout = QtWidgets.QHBoxLayout(self.quality_widget)
        self.video_group = QtWidgets.QGroupBox("Videoqualität (max. Höhe)")
        v_layout = QtWidgets.QHBoxLayout(self.video_group)
        v_layout.addWidget(self.video_quality_combo)
        self.audio_group = QtWidgets.QGroupBox("Audio-Bitrate (kbps)")
        a_layout = QtWidgets.QHBoxLayout(self.audio_group)
        a_layout.addWidget(self.audio_quality_combo)
        quality_layout.addWidget(self.video_group)
        quality_layout.addWidget(self.audio_group)
        form_layout.addRow("Qualitätseinstellungen:", self.quality_widget)
        self.update_quality_ui()

        main_layout.addLayout(form_layout)

        # Bereich für Titelanzeige und Download-Button (Download-Button unterhalb des Titels)
        top_action_layout = QtWidgets.QVBoxLayout()
        self.title_label = QtWidgets.QLabel("Titel: -")
        top_action_layout.addWidget(self.title_label)
        self.download_button = QtWidgets.QPushButton("Download starten")
        self.download_button.clicked.connect(self.start_download)
        top_action_layout.addWidget(self.download_button)
        main_layout.addLayout(top_action_layout)

        # Fortschrittsbalken für den Gesamtfortschritt aller Downloads
        self.overall_progress_bar = QtWidgets.QProgressBar()
        self.overall_progress_bar.setValue(0)
        main_layout.addWidget(self.overall_progress_bar)

        # Tabelle für Mehrfach-Downloads
        self.download_table = QtWidgets.QTableWidget(0, 4)
        self.download_table.setHorizontalHeaderLabels(["Titel", "Status", "Fortschritt", "Aktionen"])
        self.download_table.horizontalHeader().setStretchLastSection(True)
        self.download_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.download_table.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.download_table)

        self.active_downloads = {}  # {row: worker}
        self.download_progress = {}  # {row: Prozentwert}

    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Ordner wählen")
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
        elif fmt == "mp4 (ohne Audio)":
            self.video_group.show()
            self.audio_group.hide()
        elif fmt in ["avi", "mkv"]:
            self.video_group.show()
            self.audio_group.show()
        else:  # mp4 (mit Audio)
            self.video_group.show()
            self.audio_group.show()

    def start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QtWidgets.QMessageBox.critical(self, "Fehler", "Bitte eine gültige URL eingeben.")
            return
        folder = self.folder_edit.text().strip()
        if not folder:
            QtWidgets.QMessageBox.critical(self, "Fehler", "Bitte einen Download-Ordner wählen.")
            return
        fmt = self.format_combo.currentText()
        if fmt == "mp3":
            video_quality = None
            audio_bitrate = self.audio_quality_combo.currentText()
        elif fmt == "mp4 (ohne Audio)":
            video_quality = self.video_quality_combo.currentText()
            audio_bitrate = None
        else:  # mp4 (mit Audio), avi, mkv
            video_quality = self.video_quality_combo.currentText()
            audio_bitrate = self.audio_quality_combo.currentText()

        # URL-Feld leeren
        self.url_edit.clear()

        worker = DownloadWorker(url, folder, fmt, video_quality, audio_bitrate, config["DownloadOptions"])
        row = self.download_table.rowCount()
        self.download_table.insertRow(row)
        title_item = QtWidgets.QTableWidgetItem("Lade Metadaten...")
        status_item = QtWidgets.QTableWidgetItem("Wartend")
        progress_item = QtWidgets.QTableWidgetItem("0%")
        action_item = QtWidgets.QTableWidgetItem("Rechtsklick für Optionen")
        self.download_table.setItem(row, 0, title_item)
        self.download_table.setItem(row, 1, status_item)
        self.download_table.setItem(row, 2, progress_item)
        self.download_table.setItem(row, 3, action_item)
        self.active_downloads[row] = worker
        self.download_progress[row] = 0

        worker.title_signal.connect(lambda t, r=row: self.download_table.item(r, 0).setText(t))
        worker.progress_signal.connect(lambda p, s, r=row: self.update_download_row(r, p, s))
        worker.finished_signal.connect(lambda r=row: self.download_finished(r))
        worker.error_signal.connect(lambda err, r=row: self.download_error(r, err))
        worker.start()

    def update_download_row(self, row, progress, status):
        self.download_progress[row] = progress
        self.download_table.item(row, 1).setText(status)
        self.download_table.item(row, 2).setText(f"{progress:.2f}%")
        # Farbe je nach Status setzen:
        if "Pausiert" in status:
            color = QtGui.QColor("#F1C40F")  # Gelb
        elif "abgebrochen" in status or "Abbruch" in status:
            color = QtGui.QColor("#E74C3C")  # Rot
        elif "Fertig" in status:
            color = QtGui.QColor("#2ECC71")  # Grün
        else:
            color = QtGui.QColor("#95A5A6")  # Grau (läuft)
        for col in range(self.download_table.columnCount()):
            self.download_table.item(row, col).setBackground(color)
        self.update_overall_progress()

    def update_overall_progress(self):
        if self.download_progress:
            overall = sum(self.download_progress.values()) / len(self.download_progress)
        else:
            overall = 0
        self.overall_progress_bar.setValue(int(overall))

    def download_finished(self, row):
        self.download_table.item(row, 1).setText("Fertig")
        self.download_progress[row] = 100
        self.update_overall_progress()

    def download_error(self, row, err):
        self.download_table.item(row, 1).setText(f"Fehler: {err}")
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
            pause_action = menu.addAction("Fortsetzen")
        else:
            pause_action = menu.addAction("Pausieren")
        cancel_action = menu.addAction("Abbrechen")
        action = menu.exec_(self.download_table.viewport().mapToGlobal(pos))
        if action == pause_action:
            if worker._paused:
                worker.resume()
                self.download_table.item(row, 1).setText("Fortgesetzt")
            else:
                worker.pause()
                self.download_table.item(row, 1).setText("Pausiert")
        elif action == cancel_action:
            worker.cancel()
            self.download_table.item(row, 1).setText("Abgebrochen")
            # Lösche eventuell vorhandene Part-Dateien:
            if worker.current_outtmpl:
                part_file = worker.current_outtmpl + ".part"
                if os.path.exists(part_file):
                    try:
                        os.remove(part_file)
                    except Exception:
                        pass

def main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    if not check_ffmpeg():
        install = QtWidgets.QMessageBox.question(None, "ffmpeg fehlt",
                                                 "ffmpeg ist nicht installiert. Jetzt installieren?",
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if install == QtWidgets.QMessageBox.Yes:
            install_ffmpeg()
        else:
            sys.exit(1)
    # Global Dark Mode Stylesheet
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
