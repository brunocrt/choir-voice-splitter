"""Portable JSON projects. Audio references are relative whenever possible."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import os
import re
import tempfile
import uuid

PARTS = {"Tenor": (130.81, 523.25), "Bass": (65.41, 261.63),
         "Soprano": (261.63, 1046.50), "Alto": (174.61, 698.46)}
MODES = ("Range enhancement", "Demucs + range enhancement")

@dataclass
class Track:
    source: str
    part: str = "Tenor"
    mode: str = MODES[0]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    result: str | None = None
    status: str = "Ready"
    error: str = ""

@dataclass
class Project:
    name: str = "Untitled rehearsal"
    tracks: list[Track] = field(default_factory=list)
    path: Path | None = None
    dirty: bool = False

    def save(self, destination: Path) -> None:
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for track in self.tracks:
            row = asdict(track)
            for key in ("source", "result"):
                if row[key]:
                    try:
                        row[key] = os.path.relpath(row[key], destination.parent)
                    except ValueError:  # Windows drives can differ.
                        pass
            rows.append(row)
        data = {"version": 1, "name": self.name, "tracks": rows}
        descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, ensure_ascii=False)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.path, self.dirty = destination, False

    @classmethod
    def open(cls, source: Path) -> Project:
        source = source.resolve()
        if source.stat().st_size > 5_000_000:
            raise ValueError("Project file is too large.")
        data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Unsupported project version.")
        if not isinstance(data.get("tracks"), list) or len(data["tracks"]) > 1000:
            raise ValueError("Invalid project track list.")
        tracks = []
        ids = set()
        for row in data["tracks"]:
            if not isinstance(row, dict):
                raise ValueError("Invalid track.")
            values = {key: row[key] for key in Track.__dataclass_fields__ if key in row}
            if not isinstance(values.get("source"), str) or not values["source"]:
                raise ValueError("Track source must be a path.")
            if values.get("part", "Tenor") not in PARTS or values.get("mode", MODES[0]) not in MODES:
                raise ValueError("Unknown voice part or processing mode.")
            for key in ("id", "status", "error"):
                if key in values and not isinstance(values[key], str):
                    raise ValueError(f"Invalid {key}.")
            if "id" in values and not re.fullmatch(r"[0-9a-f]{32}", values["id"]):
                raise ValueError("Invalid track ID.")
            for key in ("source", "result"):
                if values.get(key) is not None:
                    if not isinstance(values[key], str):
                        raise ValueError("Invalid audio path.")
                    values[key] = str((source.parent / values[key]).resolve())
            track = Track(**values)
            if track.id in ids:
                track.id = uuid.uuid4().hex
            ids.add(track.id)
            if not Path(track.source).is_file():
                track.status = "Source missing"
            elif track.result and Path(track.result).is_file():
                track.status = "Complete"
            else:
                track.result = None
                track.status = "Ready"
            tracks.append(track)
        name = data.get("name", "Untitled rehearsal")
        if not isinstance(name, str):
            raise ValueError("Invalid project name.")
        return cls(name=name, tracks=tracks, path=source)
