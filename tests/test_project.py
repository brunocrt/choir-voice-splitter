import json
from pathlib import Path
import pytest
from choir_splitter.project import Project, Track


def test_project_round_trip_relative_paths_and_missing_files(tmp_path):
    source, result = tmp_path / "choir.wav", tmp_path / "bass.wav"
    source.touch()
    result.touch()
    project = Project("Sunday choir", [Track(str(source), "Bass", result=str(result))], dirty=True)
    file = tmp_path / "Sunday.choir"
    project.save(file)
    assert not project.dirty
    assert json.loads(file.read_text())["tracks"][0]["source"] == "choir.wav"
    loaded = Project.open(file)
    assert loaded.tracks[0].status == "Complete"
    assert loaded.tracks[0].result == str(result)
    result.unlink()
    assert Project.open(file).tracks[0].result is None
    source.unlink()
    assert Project.open(file).tracks[0].status == "Source missing"


@pytest.mark.parametrize("data", [{"version": 2}, {"version": 1, "tracks": {}},
    {"version": 1, "tracks": [{"source": 42}]},
    {"version": 1, "tracks": [{"source": "a", "part": "Unknown"}]},
    {"version": 1, "tracks": [{"source": "a", "id": "../../outside"}]}])
def test_reject_invalid_project(tmp_path, data):
    file = tmp_path / "bad.choir"
    file.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        Project.open(file)
