"""Real Qt widget tests, using the offscreen platform in headless environments."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "posix":
    os.environ.setdefault("QT_AUDIO_BACKEND", "pulseaudio")
from pathlib import Path
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QItemSelectionModel
from choir_splitter.app import MainWindow


def test_desktop_import_settings_and_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "appdata"))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        source = tmp_path / "choir.wav"
        sf.write(source, np.zeros((4410, 2)), 44100)
        window.import_paths([str(source), str(source)])
        assert window.table.rowCount() == 1
        assert window.selected()[0].source == str(source)
        window.part.setCurrentText("Bass")
        assert window.project.tracks[0].part == "Bass"
        window.project.tracks[0].result = str(tmp_path / "result.wav")
        window.part.setCurrentText("Tenor")
        assert window.project.tracks[0].result is None
        window.remove_selected()
        assert not window.project.tracks
        assert not window.run_button.isEnabled()
    finally:
        window.project.dirty = False
        window.close()
        app.processEvents()


def test_background_batch_and_portable_save(tmp_path, monkeypatch):
    import time
    from PySide6.QtTest import QTest
    from choir_splitter.project import Project
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "appdata"))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.cache = tmp_path / "working"
    try:
        for name, hz in [("first", 110), ("second", 220)]:
            source = tmp_path / f"{name}.wav"
            t = np.arange(4410) / 44100
            sf.write(source, .1 * np.sin(2 * np.pi * hz * t), 44100)
            window.import_paths([str(source)])
        window.table.selectAll()
        window.part.setCurrentText("Bass")
        assert len(window.selected()) == 2
        assert all(t.part == "Bass" for t in window.project.tracks)
        window.start_processing()
        deadline = time.monotonic() + 30
        while window.worker is not None and time.monotonic() < deadline:
            QTest.qWait(20)
        assert window.worker is None
        assert all(t.status == "Complete" for t in window.project.tracks)
        manifest = tmp_path / "Saved.choir"
        monkeypatch.setattr("choir_splitter.app.QFileDialog.getSaveFileName", lambda *_: (str(manifest), ""))
        assert window.save_project()
        assert not window.project.dirty
        loaded = Project.open(manifest)
        assert len(loaded.tracks) == 2
        assert all(Path(t.result).is_file() for t in loaded.tracks)
        assert all("Saved.assets" in t.result for t in loaded.tracks)
        # Working cache removal does not invalidate saved project results.
        import shutil
        shutil.rmtree(window.cache)
        assert all(Path(t.result).is_file() for t in Project.open(manifest).tracks)
    finally:
        if window.worker:
            window.worker.cancel.set()
            window.worker.wait(10000)
            app.processEvents()
        window.project.dirty = False
        window.close()
        app.processEvents()
