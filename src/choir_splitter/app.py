from __future__ import annotations
from pathlib import Path
from threading import Event
import shutil
import uuid

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QStandardPaths, QItemSelectionModel
from PySide6.QtGui import QAction, QColor, QCloseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFileDialog,
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSlider, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .audio import Cancelled, demucs_ready, export_audio, ffmpeg, process
from .project import MODES, PARTS, Project, Track

STYLE = """
QMainWindow, QWidget { background: #101719; color: #e7eeeb; font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 13px; }
QLabel#brand { color: #99ddba; font-size: 12px; font-weight: 700; letter-spacing: 2px; }
QLabel#title { font-size: 32px; font-weight: 600; }
QLabel#muted { color: #a1b2ac; }
QFrame#card { background: #192325; border: 1px solid #30413d; border-radius: 12px; }
QFrame#card QLabel, QFrame#card QWidget { background: transparent; }
QPushButton { background: #24332f; border: 1px solid #3a5147; border-radius: 7px; padding: 10px 17px; font-weight: 600; }
QPushButton:hover { background: #344c40; }
QPushButton:disabled { color: #62736c; border-color: #28362f; background: #1a2520; }
QPushButton#primary { background: #b5e6c7; color: #14281d; border: none; }
QPushButton#primary:hover { background: #cef4dc; }
QComboBox { padding: 8px 12px; background: #202e2b; border: 1px solid #42584e; border-radius: 6px; min-height: 20px; }
QComboBox QAbstractItemView { background: #202e2b; selection-background-color: #3f6451; }
QTableWidget { background: #15201e; border: 1px solid #30413d; border-radius: 8px; gridline-color: #293a34; selection-background-color: #304e3f; }
QTableWidget::item { padding: 12px; }
QHeaderView::section { background: #1e2c27; color: #9ab3a6; border: none; padding: 12px; font-size: 11px; font-weight: 700; }
QProgressBar { border: none; background: #26352f; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #a7dfba; border-radius: 4px; }
QSlider::groove:horizontal { background: #34483e; height: 5px; border-radius: 2px; }
QSlider::handle:horizontal { background: #b5e6c7; width: 13px; margin: -4px 0; border-radius: 6px; }
QMenuBar, QMenu { background: #192623; }
QMenu::item:selected { background: #3f6451; }
QStatusBar { color: #98afa2; }
"""

class BatchWorker(QThread):
    progress = Signal(str, int, str)
    completed = Signal(str, str)
    failed = Signal(str, str)
    cancelled = Signal()

    def __init__(self, tracks: list[Track], folder: Path, device: str):
        super().__init__()
        self.tracks = tracks
        self.folder, self.device = folder, device
        self.cancel = Event()

    def run(self):
        for track in self.tracks:
            if self.cancel.is_set():
                self.cancelled.emit()
                return
            try:
                # A unique result per run preserves existing saved projects.
                target = self.folder / f"{track.id}-{uuid.uuid4().hex[:8]}.wav"
                result = process(Path(track.source), target, track.part, track.mode, self.device,
                    self.cancel, lambda value, message: self.progress.emit(track.id, value, message))
                self.completed.emit(track.id, str(result))
            except Cancelled:
                self.cancelled.emit()
                return
            except Exception as error:
                self.failed.emit(track.id, str(error))


class ExportWorker(QThread):
    failed = Signal(str)
    succeeded = Signal(str)

    def __init__(self, pairs):
        super().__init__()
        self.pairs = pairs
        self.cancel = Event()

    def run(self):
        try:
            for source, destination in self.pairs:
                if self.cancel.is_set():
                    raise Cancelled()
                export_audio(source, destination, self.cancel)
            self.succeeded.emit(f"Exported {len(self.pairs)} recording(s).")
        except Cancelled:
            self.failed.emit("Export cancelled. Previously completed exports are available.")
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = Project()
        self.worker = None
        self.pending_close = False
        self.setWindowTitle("Choir Voice Splitter")
        self.resize(1120, 820)
        self.setMinimumSize(900, 740)
        self.setAcceptDrops(True)
        self.cache = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / "results"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(.8)
        self.player.setAudioOutput(self.audio_output)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.positionChanged.connect(self.position_changed)
        self.player.errorOccurred.connect(lambda *_: self.statusBar().showMessage(self.player.errorString(), 12000))
        self.player.playbackStateChanged.connect(lambda state: self.play_button.setText("Pause" if state == QMediaPlayer.PlayingState else "Play"))
        self.build_ui()
        self.build_menu()
        self.refresh()
        self.statusBar().showMessage("Local processing · Your recordings stay on this computer")

    def build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 24, 30, 20)
        layout.setSpacing(16)
        top = QHBoxLayout()
        brand = QLabel("◉  CHOIR / REHEARSAL STUDIO")
        brand.setObjectName("brand")
        top.addWidget(brand)
        top.addStretch()
        local = QLabel("●  OFFLINE WORKSPACE")
        local.setObjectName("muted")
        top.addWidget(local)
        layout.addLayout(top)
        title = QLabel("Find your voice in the choir.")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("Bring in a recording. Focus on your part. Rehearse at your own pace.")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        actions = QHBoxLayout()
        self.add_button = QPushButton("+  Add recordings")
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self.add_files)
        actions.addWidget(self.add_button)
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.clicked.connect(self.remove_selected)
        actions.addWidget(self.remove_button)
        actions.addStretch()
        self.project_label = QLabel("Untitled rehearsal")
        self.project_label.setObjectName("muted")
        actions.addWidget(self.project_label)
        layout.addLayout(actions)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["RECORDING", "VOICE PART", "METHOD", "STATUS"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 330)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 230)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.table, 1)
        self.empty_label = QLabel("Drop MP3, WAV, M4A, AAC, OGG or OPUS recordings here to begin.")
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_label)

        card = QFrame()
        card.setObjectName("card")
        settings = QVBoxLayout(card)
        settings.setContentsMargins(18, 14, 18, 14)
        row = QHBoxLayout()
        row.addWidget(QLabel("Voice part"))
        self.part = QComboBox()
        self.part.addItems(PARTS)
        self.part.currentTextChanged.connect(self.settings_changed)
        row.addWidget(self.part)
        row.addSpacing(15)
        row.addWidget(QLabel("Processing"))
        self.mode = QComboBox()
        self.mode.addItems(MODES)
        self.mode.currentTextChanged.connect(self.settings_changed)
        row.addWidget(self.mode, 1)
        self.device = QComboBox()
        self.device.addItems(["CPU", "NVIDIA CUDA"])
        self.device.setToolTip("CUDA requires a compatible NVIDIA GPU and CUDA-enabled PyTorch.")
        row.addWidget(self.device)
        settings.addLayout(row)
        caveat = QLabel("Range enhancement emphasizes a vocal register; overlapping singers and instruments may remain.\nDemucs removes accompaniment first. Neither mode guarantees isolated SATB parts. Tenor and Bass are the V1 focus.")
        caveat.setObjectName("muted")
        caveat.setWordWrap(True)
        settings.addWidget(caveat)
        layout.addWidget(card)
        progress_row = QHBoxLayout()
        self.run_button = QPushButton("Enhance all recordings")
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self.start_processing)
        progress_row.addWidget(self.run_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_processing)
        progress_row.addWidget(self.cancel_button)
        self.progress_label = QLabel("Ready when you are")
        self.progress_label.setObjectName("muted")
        progress_row.addWidget(self.progress_label, 1)
        layout.addLayout(progress_row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        playback = QFrame()
        playback.setObjectName("card")
        pl = QVBoxLayout(playback)
        pl.setContentsMargins(18, 14, 18, 14)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("LISTEN & PRACTICE"))
        controls.addStretch()
        self.preview = QComboBox()
        self.preview.addItems(["Original recording", "Enhanced voice"])
        self.preview.currentIndexChanged.connect(self.load_preview)
        controls.addWidget(self.preview)
        self.speed = QComboBox()
        self.speed.addItems(["0.75×", "1.0×", "1.25×"])
        self.speed.setCurrentIndex(1)
        self.speed.currentIndexChanged.connect(lambda i: self.player.setPlaybackRate([.75, 1, 1.25][i]))
        controls.addWidget(self.speed)
        pl.addLayout(controls)
        transport = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        transport.addWidget(self.play_button)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.sliderMoved.connect(self.player.setPosition)
        transport.addWidget(self.seek, 1)
        self.time_label = QLabel("0:00 / 0:00")
        transport.addWidget(self.time_label)
        self.export_button = QPushButton("Export selected…")
        self.export_button.clicked.connect(self.export_selected)
        transport.addWidget(self.export_button)
        pl.addLayout(transport)
        layout.addWidget(playback)
        self.setCentralWidget(root)

    def build_menu(self):
        menu = self.menuBar().addMenu("Project")
        self.project_actions = []
        for title, shortcut, handler in [("New project", "Ctrl+N", self.new_project),
            ("Open project…", "Ctrl+O", self.open_project), ("Save project", "Ctrl+S", self.save_project),
            ("Save project as…", "Ctrl+Shift+S", lambda: self.save_project(True))]:
            action = QAction(title, self)
            action.setShortcut(shortcut)
            action.triggered.connect(handler)
            menu.addAction(action)
            self.project_actions.append(action)
        help_menu = self.menuBar().addMenu("Help")
        action = help_menu.addAction("Setup & model status")
        action.triggered.connect(self.show_setup)
        action = help_menu.addAction("About")
        action.triggered.connect(lambda: QMessageBox.information(self, "About Choir Voice Splitter",
            "Choir Voice Splitter 0.1.0\nOffline choir rehearsal tools.\n\nThis version provides voice-range enhancement, not learned SATB separation.\nListen before relying on a result for practice.\nPlayback speed changes may affect pitch depending on your multimedia backend."))

    def selected(self):
        return [self.project.tracks[i.row()] for i in sorted(self.table.selectionModel().selectedRows(), key=lambda x: x.row())]

    def refresh(self):
        previous = {track.id for track in self.selected()} if self.table.rowCount() == len(self.project.tracks) else set()
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.project.tracks))
        for index, track in enumerate(self.project.tracks):
            for column, value in enumerate((Path(track.source).name, track.part, track.mode, track.status)):
                item = QTableWidgetItem(value)
                item.setToolTip(track.error or track.source)
                if column == 3:
                    item.setForeground(QColor("#b6e6c8" if track.status == "Complete" else "#a7b8b0"))
                self.table.setItem(index, column, item)
            self.table.setRowHeight(index, 50)
        self.table.clearSelection()
        for index, track in enumerate(self.project.tracks):
            if track.id in previous:
                self.table.selectionModel().select(self.table.model().index(index, 0),
                    QItemSelectionModel.Select | QItemSelectionModel.Rows)
        self.table.blockSignals(False)
        self.empty_label.setVisible(not self.project.tracks)
        self.project_label.setText(self.project.name + (" •" if self.project.dirty else ""))
        self.setWindowTitle(f"{self.project.name}{' *' if self.project.dirty else ''} — Choir Voice Splitter")
        self.update_enabled()

    def update_enabled(self):
        busy = self.worker is not None
        for control in (self.add_button, self.remove_button, self.part, self.mode, self.device, *self.project_actions):
            control.setEnabled(not busy)
        self.table.setEnabled(not busy)
        self.run_button.setEnabled(bool(self.project.tracks) and not busy)
        self.cancel_button.setEnabled(busy)
        tracks = self.selected()
        self.export_button.setEnabled(not busy and any(t.result and Path(t.result).is_file() for t in tracks))
        self.play_button.setEnabled(bool(tracks))

    def selection_changed(self):
        tracks = self.selected()
        if tracks:
            for combo, value in ((self.part, tracks[0].part), (self.mode, tracks[0].mode)):
                combo.blockSignals(True)
                combo.setCurrentText(value)
                combo.blockSignals(False)
        self.load_preview()
        self.update_enabled()

    def settings_changed(self):
        for track in self.selected():
            if (track.part, track.mode) != (self.part.currentText(), self.mode.currentText()):
                track.part, track.mode = self.part.currentText(), self.mode.currentText()
                track.result, track.status, track.error = None, "Ready", ""
                self.project.dirty = True
        self.refresh()
        self.load_preview()

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add choir recordings", "", "Audio (*.mp3 *.wav *.m4a *.aac *.ogg *.opus *.wma *.flac);;All files (*)")
        self.import_paths(paths)

    def import_paths(self, paths):
        existing = {t.source for t in self.project.tracks}
        for path in paths:
            resolved = str(Path(path).resolve())
            if Path(resolved).is_file() and resolved not in existing:
                self.project.tracks.append(Track(resolved, self.part.currentText(), self.mode.currentText()))
                existing.add(resolved)
                self.project.dirty = True
        self.refresh()
        if self.project.tracks and not self.selected():
            self.table.selectRow(len(self.project.tracks) - 1)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not self.worker:
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.worker:
            self.import_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])

    def remove_selected(self):
        ids = {t.id for t in self.selected()}
        if ids:
            self.player.stop()
            self.project.tracks = [t for t in self.project.tracks if t.id not in ids]
            self.project.dirty = True
            self.table.clearSelection()
            self.refresh()
            self.load_preview()

    def start_processing(self):
        try:
            ffmpeg()
            if any(t.mode == MODES[1] for t in self.project.tracks) and not demucs_ready():
                self.show_setup()
                return
        except Exception as error:
            self.show_error(str(error))
            return
        self.player.stop()
        self.worker = BatchWorker(list(self.project.tracks), self.cache,
                                  "cuda" if self.device.currentIndex() else "cpu")
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.on_complete)
        self.worker.failed.connect(self.on_failure)
        self.worker.cancelled.connect(lambda: self.progress_label.setText("Cancelled · completed results kept"))
        self.worker.finished.connect(self.worker_finished)
        self.progress.setValue(0)
        self.progress_label.setText("Starting batch…")
        self.update_enabled()
        self.worker.start()

    def find_track(self, track_id):
        return next(t for t in self.project.tracks if t.id == track_id)

    def on_progress(self, track_id, value, message):
        track = self.find_track(track_id)
        track.status = "Processing"
        self.progress.setValue(value)
        self.progress_label.setText(message)
        self.refresh()

    def on_complete(self, track_id, result):
        track = self.find_track(track_id)
        track.result, track.status, track.error = result, "Complete", ""
        self.project.dirty = True
        self.refresh()
        self.statusBar().showMessage(f"Ready to preview: {Path(track.source).name}")

    def on_failure(self, track_id, message):
        track = self.find_track(track_id)
        track.status, track.error = "Failed", message
        self.project.dirty = True
        self.refresh()
        self.statusBar().showMessage(message, 20000)

    def worker_finished(self):
        worker = self.worker
        self.worker = None
        worker.deleteLater()
        for track in self.project.tracks:
            if track.status == "Processing":
                track.status = "Complete" if track.result else "Ready"
        self.refresh()
        if isinstance(worker, BatchWorker):
            complete = sum(t.status == "Complete" for t in self.project.tracks)
            failed = sum(t.status == "Failed" for t in self.project.tracks)
            self.progress_label.setText(f"{complete} complete · {failed} failed" + (" · cancelled" if worker.cancel.is_set() else ""))
        self.load_preview()
        if self.pending_close:
            self.pending_close = False
            self.close()

    def cancel_processing(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.progress_label.setText("Cancelling…")

    def load_preview(self):
        self.player.stop()
        tracks = self.selected()
        path = None
        if tracks:
            path = tracks[0].result if self.preview.currentIndex() == 1 else tracks[0].source
        self.player.setSource(QUrl.fromLocalFile(path) if path and Path(path).is_file() else QUrl())
        if tracks and self.preview.currentIndex() == 1 and not path:
            self.statusBar().showMessage("Process this recording to preview the enhanced voice.", 6000)

    def toggle_play(self):
        if self.player.source().isEmpty():
            self.statusBar().showMessage("Select an available recording or process it first.", 6000)
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    @staticmethod
    def time_text(milliseconds):
        seconds = milliseconds // 1000
        return f"{seconds // 60}:{seconds % 60:02d}"

    def duration_changed(self, duration):
        self.seek.setRange(0, duration)
        self.position_changed(self.player.position())

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)
        self.time_label.setText(f"{self.time_text(position)} / {self.time_text(self.player.duration())}")

    def export_selected(self):
        tracks = [t for t in self.selected() if t.result and Path(t.result).is_file()]
        if not tracks:
            return
        pairs = []
        if len(tracks) == 1:
            track = tracks[0]
            path, selected_filter = QFileDialog.getSaveFileName(self, "Export enhanced recording", f"{Path(track.source).stem}-{track.part.lower()}.mp3", "MP3 (*.mp3);;WAV (*.wav)")
            if not path:
                return
            target = Path(path)
            if not target.suffix:
                target = target.with_suffix(".wav" if selected_filter.startswith("WAV") else ".mp3")
            pairs.append((Path(track.result), target))
        else:
            directory = QFileDialog.getExistingDirectory(self, "Export selected recordings as MP3")
            if not directory:
                return
            for track in tracks:
                target = Path(directory) / f"{Path(track.source).stem}-{track.part.lower()}-{track.id[:6]}.mp3"
                pairs.append((Path(track.result), target))
            if any(target.exists() for _, target in pairs):
                if QMessageBox.question(self, "Replace exports?", "Some exports already exist. Replace them?") != QMessageBox.Yes:
                    return
        # Never overwrite an imported recording, even if the file picker allows it.
        originals = {Path(t.source).resolve() for t in self.project.tracks}
        if any(target.resolve() in originals for _, target in pairs):
            self.show_error("Choose an export path different from every imported recording.")
            return
        self.worker = ExportWorker(pairs)
        self.worker.failed.connect(self.show_error)
        self.worker.succeeded.connect(lambda message: self.statusBar().showMessage(message, 12000))
        self.worker.finished.connect(self.worker_finished)
        self.progress_label.setText("Exporting…")
        self.update_enabled()
        self.worker.start()

    def maybe_save(self):
        if not self.project.dirty:
            return True
        answer = QMessageBox.question(self, "Save rehearsal?", "Save changes to this project?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Cancel:
            return False
        return self.save_project() if answer == QMessageBox.Save else True

    def save_project(self, save_as=False):
        path = self.project.path
        if save_as or not path:
            chosen, _ = QFileDialog.getSaveFileName(self, "Save project", str(path or "Rehearsal.choir"), "Choir project (*.choir)")
            if not chosen:
                return False
            path = Path(chosen)
            if path.suffix != ".choir":
                path = path.with_suffix(".choir")
        try:
            # Copy generated results alongside the manifest for portable output.
            assets = path.parent / (path.stem + ".assets")
            saved = []
            for track in self.project.tracks:
                if track.result and Path(track.result).is_file():
                    assets.mkdir(parents=True, exist_ok=True)
                    target = assets / f"{track.id}-{Path(track.result).stem}.wav"
                    if Path(track.result).resolve().parent == assets.resolve():
                        target = Path(track.result)
                    if target.resolve() != Path(track.result).resolve():
                        shutil.copy2(track.result, target)
                    saved.append((track, track.result, str(target.resolve())))
            for track, _, target in saved:
                track.result = target
            old_name = self.project.name
            self.project.name = path.stem
            try:
                self.project.save(path)
            except Exception:
                self.project.name = old_name
                for track, old_result, _ in saved:
                    track.result = old_result
                raise
            self.refresh()
            return True
        except Exception as error:
            self.show_error(str(error))
            return False

    def new_project(self):
        if self.maybe_save():
            self.player.stop()
            self.table.clearSelection()
            self.project = Project()
            self.refresh()
            self.load_preview()

    def open_project(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open project", "", "Choir project (*.choir)")
        if path:
            try:
                project = Project.open(Path(path))
                self.player.stop()
                self.table.clearSelection()
                self.project = project
                self.refresh()
                if project.tracks:
                    self.table.selectRow(0)
            except Exception as error:
                self.show_error(str(error))

    def show_setup(self):
        try:
            executable = ffmpeg()
        except RuntimeError:
            executable = "Not installed"
        QMessageBox.information(self, "Setup & model status",
            f"FFmpeg: {executable}\nHT-Demucs: {'Cached and installed' if demucs_ready() else 'Not ready'}\n\n"
            "Range enhancement runs offline without AI weights.\n\n"
            "Optional AI setup (in your Python environment):\n"
            'pip install -e ".[ai]"\n'
            "python -m choir_splitter --prepare-model\n\n"
            "Model preparation downloads pretrained weights and requires internet. "
            "Subsequent processing uses the local cache. See README for platform setup. "
            "This model separates vocals from accompaniment, not SATB sections.")

    def show_error(self, message):
        QMessageBox.warning(self, "Choir Voice Splitter", message)

    def closeEvent(self, event: QCloseEvent):
        if self.worker:
            self.pending_close = True
            self.cancel_processing()
            event.ignore()
            return
        if self.maybe_save():
            self.player.stop()
            event.accept()
        else:
            event.ignore()


def launch():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Choir Voice Splitter")
    app.setOrganizationName("ChoirTools")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()
