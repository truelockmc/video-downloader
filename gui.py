#!/usr/bin/env python3
"""
UI (MainWindow) - uses utils and workers.
Includes:
 - filename-change dialog before starting a download
 - automatic uniqueness check (appends " (1)", " (2)", ...) if file exists
 - forwards a forced_outtmpl to DownloadWorker
"""

import os
import random
import signal
import sys

from gui_styling import modern_stylesheet
from PyQt6 import QtCore, QtGui, QtWidgets
from utils import (
    CONFIG_FILE,
    check_ffmpeg,
    install_ffmpeg,
    load_or_create_config,
    sanitize_filename,
    unique_filename,
)
from workers import DownloadWorker, MetadataWorker

config = load_or_create_config()


class HoverTooltip(QtWidgets.QWidget):
    """Custom hover tooltip that displays over the table"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Set as a top-level widget to avoid event issues
        self.setWindowFlags(
            QtCore.Qt.WindowType.ToolTip | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container with border
        container = QtWidgets.QWidget()
        container.setStyleSheet(
            """
            background-color: #1a1a1a;
            border: 2px solid #0D47A1;
            border-radius: 6px;
        """
        )
        container.setMouseTracking(True)
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(6)

        # Thumbnail
        self.thumbnail = QtWidgets.QLabel()
        self.thumbnail.setFixedSize(140, 90)
        self.thumbnail.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setStyleSheet("border: 1px solid #333; border-radius: 4px;")
        self.thumbnail.setMouseTracking(True)
        container_layout.addWidget(self.thumbnail)

        # Title
        self.title_label = QtWidgets.QLabel()
        self.title_label.setStyleSheet(
            "color: #d0d0d0; font-weight: bold; font-size: 8pt;"
        )
        self.title_label.setWordWrap(True)
        self.title_label.setFixedWidth(150)
        self.title_label.setMinimumHeight(40)
        self.title_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft
        )
        self.title_label.setMouseTracking(True)
        container_layout.addWidget(self.title_label)

        # Filepath
        self.filepath_label = QtWidgets.QLabel()
        self.filepath_label.setStyleSheet("color: #808080; font-size: 7pt;")
        self.filepath_label.setWordWrap(True)
        self.filepath_label.setFixedWidth(150)
        self.filepath_label.setMinimumHeight(30)
        self.filepath_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft
        )
        self.filepath_label.setMouseTracking(True)
        container_layout.addWidget(self.filepath_label)

        layout.addWidget(container)

        # Set fixed size to prevent resizing flicker
        self.setFixedSize(170, 220)
        self.hide()

        # Store filepath for click handler
        self.current_filepath = ""

    def show_tooltip(self, title, filename, filepath, thumbnail_pixmap, pos):
        """Show tooltip at given position (global screen coordinates)"""
        self.title_label.setText(f"{title}")
        self.filepath_label.setText(f"{filepath}")
        self.current_filepath = filepath

        if thumbnail_pixmap:
            scaled = thumbnail_pixmap.scaled(
                140,
                90,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.thumbnail.setPixmap(scaled)
        else:
            self.thumbnail.setText("No Preview")

        # Move to position and show
        self.move(pos)
        self.raise_()
        self.show()

    def mousePressEvent(self, event):
        """Open file manager and select the file when clicked"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.open_in_file_manager()
            event.accept()
        else:
            super().mousePressEvent(event)

    def enterEvent(self, event):
        """Mouse entered the tooltip - keep it visible"""
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse left the tooltip - hide it"""
        self.hide()
        super().leaveEvent(event)

    def open_in_file_manager(self):
        if not self.current_filepath or self.current_filepath == "Unknown":
            return

        filepath = self.current_filepath
        if not os.path.exists(filepath):
            return

        import platform
        import subprocess

        system = platform.system()

        try:
            if system == "Windows":
                # Windows
                subprocess.run(["explorer", "/select,", filepath])
            elif system == "Darwin":
                # macOS
                subprocess.run(["open", "-R", filepath])
            elif system == "Linux":
                # Linux
                folder = os.path.dirname(filepath)
                # Try xdg-open
                try:
                    subprocess.run(["xdg-open", folder])
                except:
                    # Fallback to common file managers
                    for fm in ["nautilus", "dolphin", "thunar", "nemo", "caja"]:
                        try:
                            subprocess.run([fm, folder])
                            break
                        except:
                            continue
        except Exception:
            print("failed to open File")
            pass


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Downloader UI")
        self.resize(700, 600)

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
        examples = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.instagram.com/p/ABC123...",
            "https://www.tiktok.com/@user/video/123456",
        ]

        self.url_edit = QtWidgets.QLineEdit()
        self.url_edit.setPlaceholderText(f"e.g. {random.choice(examples)}")
        form_layout.addRow("Video URL:", self.url_edit)
        self.url_edit.textChanged.connect(self.on_url_changed)

        self.url_error_label = QtWidgets.QLabel("❌ No valid URL or unsupported Site!")
        self.url_error_label.setStyleSheet(
            "color: #ff6b6b; font-weight: bold; font-size: 9pt; margin-top: 4px;"
        )
        self.url_error_label.setVisible(False)
        form_layout.addRow("", self.url_error_label)

        self.error_animation = QtCore.QPropertyAnimation(
            self.url_error_label, b"geometry"
        )
        self.error_animation.setDuration(200)

        folder_layout = QtWidgets.QHBoxLayout()
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_edit.setText(
            config["DownloadOptions"].get("download_folder", os.path.expanduser("~"))
        )
        folder_button = QtWidgets.QPushButton("Choose Folder")
        folder_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(folder_button)
        form_layout.addRow("Download Folder:", folder_layout)

        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(
            ["mp4 (with Audio)", "mp4 (without Audio)", "mp3", "avi", "mkv"]
        )
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
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedHeight(200)
        self.thumbnail_label.hide()
        main_layout.addWidget(self.thumbnail_label)

        self.preview_title = QtWidgets.QLabel("")
        main_layout.addWidget(self.preview_title)

        # Download button
        top_action_layout = QtWidgets.QVBoxLayout()
        self.download_button = QtWidgets.QPushButton("Start Download")
        self.download_button.setEnabled(False)  # deactivated initially
        self.download_button.clicked.connect(self.start_download)
        top_action_layout.addWidget(self.download_button)
        main_layout.addLayout(top_action_layout)

        # Overall progress bar
        self.overall_progress_bar = QtWidgets.QProgressBar()
        self.overall_progress_bar.setValue(0)
        main_layout.addWidget(self.overall_progress_bar)

        # Download table
        self.download_table = QtWidgets.QTableWidget(0, 5)
        self.download_table.setHorizontalHeaderLabels(
            ["Title", "Status", "Progress", "Size", "Actions"]
        )
        self.download_table.horizontalHeader().setStretchLastSection(True)
        self.download_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.download_table.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.download_table.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.download_table)

        # Hover tooltip
        self.hover_tooltip = HoverTooltip(self)
        self.hover_timer = QtCore.QTimer()
        self.hover_timer.timeout.connect(self.show_hover_tooltip)
        self.hide_timer = QtCore.QTimer()
        self.hide_timer.timeout.connect(self.hide_hover_tooltip)
        self.download_table.setMouseTracking(True)
        self.download_table.cellEntered.connect(self.on_table_cell_entered)

        # Detect when mouse leaves the table
        self.download_table.viewport().installEventFilter(self)

        self.active_downloads = {}
        self.download_progress = {}
        self.last_hovered_row = -1

    def on_table_cell_entered(self, row, col):
        """Called when mouse enters a table cell"""
        if row != self.last_hovered_row or not self.hover_tooltip.isVisible():
            self.last_hovered_row = row
            self.hover_timer.stop()
            self.hide_timer.stop()
            self.hover_tooltip.hide()
            self.hover_timer.start(500)

    def eventFilter(self, obj, event):
        """Filter events to detect when mouse leaves the table"""
        if obj == self.download_table.viewport():
            if event.type() == QtCore.QEvent.Type.Leave:
                if not self.hover_tooltip.isVisible():
                    self.hide_timer.start(300)
                else:
                    self.hide_timer.start(800)
                    self.last_hovered_row = -1
            elif event.type() == QtCore.QEvent.Type.Enter:
                self.hide_timer.stop()
        return super().eventFilter(obj, event)

    def hide_hover_tooltip(self):
        """Hide the tooltip after delay, unless mouse is over it"""
        if not self.hover_tooltip.underMouse():
            self.hover_tooltip.hide()
            self.hover_timer.stop()
            self.hide_timer.stop()
        else:
            self.hide_timer.stop()

    def show_hover_tooltip(self):
        """Show the tooltip after 1.5 seconds"""
        if self.last_hovered_row < 0:
            return

        row = self.last_hovered_row
        title = self.download_table.item(row, 0).text()

        # Extract Information
        worker = self.active_downloads.get(row)
        filename = "Unknown"
        filepath = "Unknown"
        thumbnail = None

        if worker:
            # Get filepath from worker
            if hasattr(worker, "current_outtmpl") and worker.current_outtmpl:
                filepath = worker.current_outtmpl
                filename = os.path.basename(filepath)

            if hasattr(worker, "cached_metadata") and worker.cached_metadata:
                if "thumbnail" in worker.cached_metadata:
                    thumbnail = worker.cached_metadata.get("thumbnail")

        if (
            not thumbnail
            and self.cached_metadata
            and "thumbnail" in self.cached_metadata
        ):
            thumbnail = self.cached_metadata.get("thumbnail")

        # Calculate position in global screen coordinates
        rect = self.download_table.visualItemRect(self.download_table.item(row, 0))
        table_viewport_pos = self.download_table.viewport().mapToGlobal(rect.topRight())

        tooltip_pos = QtCore.QPoint(table_viewport_pos.x() + 15, table_viewport_pos.y())

        self.hover_tooltip.show_tooltip(
            title, filename, filepath, thumbnail, tooltip_pos
        )

    def mouseleaveEvent(self, event):
        """Hide tooltip when leaving window"""
        if not self.download_table.underMouse():
            self.hover_timer.stop()
            self.hover_tooltip.hide()
        super().mouseleaveEvent(event)

    def on_url_changed(self, text):
        url = self.url_edit.text().strip()

        # Hide error on empty input
        if not url:
            self.url_error_label.setVisible(False)
            self.preview_title.setText("")
            self.thumbnail_label.hide()
            self.download_button.setEnabled(False)
            return

        if url == self.last_url:
            return

        self.last_url = url

        # Show loading state
        self.preview_title.setText("Fetching metadata...")
        self.thumbnail_label.setText("Loading thumbnail...")
        self.thumbnail_label.show()
        self.download_button.setEnabled(False)

        self.metadata_worker = MetadataWorker(url)
        self.metadata_worker.metadata_signal.connect(self.on_metadata_received)
        self.metadata_worker.error_signal.connect(self.on_metadata_error)
        self.metadata_worker.start()

    def on_metadata_error(self, error_message):
        """Handle metadata error from yt-dlp"""
        self.url_error_label.setVisible(True)
        self.url_error_label.setText("❌ No valid URL or unsupported Site!")
        self.preview_title.setText("")
        self.thumbnail_label.hide()
        self.download_button.setEnabled(False)

    def on_metadata_received(self, metadata):
        """Handle successful metadata retrieval"""
        self.url_error_label.setVisible(False)

        current_url = self.url_edit.text().strip()
        if current_url != "":
            self.cached_url = current_url
            self.cached_metadata = metadata

        title = metadata.get("title", "")
        self.preview_title.setText(title)
        font = self.preview_title.font()
        font.setBold(True)
        font.setPointSize(11)
        self.preview_title.setFont(font)

        pixmap = metadata.get("thumbnail")
        if pixmap:
            scaled = pixmap.scaled(
                self.thumbnail_label.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.thumbnail_label.setPixmap(scaled)
        else:
            self.thumbnail_label.hide()

        self.download_button.setEnabled(True)

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

    def start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QtWidgets.QMessageBox.critical(
                self, "Error", "Please enter a valid file URL."
            )
            return
        folder = self.folder_edit.text().strip()
        if not folder:
            QtWidgets.QMessageBox.critical(
                self, "Error", "Please choose a download folder."
            )
            return
        fmt = self.format_combo.currentText()
        if fmt == "mp3":
            video_quality = None
            audio_bitrate = self.audio_quality_combo.currentText()
            default_ext = "mp3"
        elif fmt == "mp4 (without Audio)":
            video_quality = self.video_quality_combo.currentText()
            audio_bitrate = None
            default_ext = "mp4"
        else:
            video_quality = self.video_quality_combo.currentText()
            audio_bitrate = self.audio_quality_combo.currentText()
            default_ext = "mp4"

        # Determine suggested filename
        if self.cached_url == url and self.cached_metadata:
            suggested = self.cached_metadata.get("title", "")
        else:
            # fallback: use last path segment of URL or 'download'
            try:
                suggested = os.path.splitext(os.path.basename(url))[0] or "download"
            except Exception:
                suggested = "download"
        suggested = sanitize_filename(suggested)

        # Ask user for filename (without extension)
        base_name, ok = QtWidgets.QInputDialog.getText(
            self, "Filename", f"Save as (without extension):", text=suggested
        )
        if not ok:
            return  # user cancelled
        base_name = base_name.strip()
        if not base_name:
            base_name = suggested

        # Create a unique filename in the folder (append (1), (2) ... if exists)
        final_fullpath = unique_filename(folder, base_name, default_ext)

        # Prepare worker with forced_outtmpl = final_fullpath
        worker = DownloadWorker(
            url,
            folder,
            fmt,
            video_quality,
            audio_bitrate,
            config["DownloadOptions"],
            cached_metadata=(self.cached_metadata if self.cached_url == url else None),
            forced_outtmpl=final_fullpath,
        )
        row = self.download_table.rowCount()
        self.download_table.insertRow(row)
        for col, text in enumerate(
            [
                "Loading metadata...",
                "Waiting",
                "0%",
                "Unknown",
                "Right click for options",
            ]
        ):
            item = QtWidgets.QTableWidgetItem(text)
            item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.download_table.setItem(row, col, item)
        self.active_downloads[row] = worker
        self.download_progress[row] = 0

        worker.title_signal.connect(
            lambda t, r=row: self.download_table.item(r, 0).setText(t)
        )
        worker.progress_signal.connect(
            lambda p, s, r=row: self.update_download_row(r, p, s)
        )
        worker.size_signal.connect(
            lambda s, r=row: self.download_table.item(r, 3).setText(s)
        )
        worker.finished_signal.connect(lambda r=row: self.download_finished(r))
        worker.error_signal.connect(lambda err, r=row: self.download_error(r, err))
        worker.start()
        self.url_edit.clear()

    def update_download_row(self, row, progress, status):
        self.download_progress[row] = progress
        self.download_table.item(row, 1).setText(status)
        self.download_table.item(row, 2).setText(f"{progress:.2f}%")
        if "paused" in status.lower():
            color = QtGui.QColor("#F39C12")  # Orange
        elif "cancelled" in status.lower():
            color = QtGui.QColor("#E74C3C")  # Red
        elif "finished" in status.lower():
            color = QtGui.QColor("#2ECC71")  # Green
        elif "waiting" in status.lower():
            color = QtGui.QColor("#F1C40F")  # Light yellow
        elif "downloading" in status.lower():
            color = QtGui.QColor("#3498DB")  # Blue
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
                progress = float(
                    self.download_table.item(row, 2).text().replace("%", "")
                )
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
        action = menu.exec(self.download_table.viewport().mapToGlobal(pos))
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

    def closeEvent(self, event):
        """
        Intercept window close:
         - if active downloads exist -> ask confirmation (EN)
         - if confirmed: cancel downloads, wait shortly, run cleanup in configured folder
         - always run cleanup (best-effort)
        """
        # Find running workers
        running_workers = []
        for w in self.active_downloads.values():
            try:
                if w.isRunning() and not getattr(w, "_cancelled", False):
                    running_workers.append(w)
            except Exception:
                running_workers.append(w)

        if running_workers:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Active downloads",
                "There are active downloads. Are you sure you want to quit? This will cancel all active downloads.",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.No:
                event.ignore()
                return
            # else: cancel all
            for w in running_workers:
                try:
                    w.cancel()
                except Exception:
                    pass
            # wait a moment for threads to stop (best-effort)
            for w in running_workers:
                try:
                    w.wait(3000)
                except Exception:
                    pass

        # Cleanup download folder always (best-effort)
        try:
            folder = config["DownloadOptions"].get(
                "download_folder", os.path.expanduser("~")
            )
            from utils import cleanup_download_folder

            cleanup_download_folder(folder)
        except Exception:
            pass

        event.accept()


def main_app():
    app = QtWidgets.QApplication(sys.argv)
    if not check_ffmpeg():
        install = QtWidgets.QMessageBox.question(
            None,
            "ffmpeg missing",
            "ffmpeg is not installed. Install now?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
        )
        if install == QtWidgets.QMessageBox.StandardButton.Yes:
            install_ffmpeg()
        else:
            sys.exit(1)
    modern_stylesheet(app)
    window = MainWindow()
    sigint_received = False

    # Ensure Ctrl+C triggers the same close flow: post a close() to the window
    def _sigint_handler(signum, frame):
        nonlocal sigint_received
        if sigint_received:
            print("\nForce quit...")
            os._exit(1)
        sigint_received = True
        try:
            QtCore.QMetaObject.invokeMethod(
                window, "close", QtCore.Qt.ConnectionType.QueuedConnection
            )
        except Exception:
            # fallback: exit
            os._exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)  # Wake up Qt event loop
    timer.start(500)

    window.show()
    sys.exit(app.exec())
