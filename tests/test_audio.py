from pathlib import Path
from threading import Event
import shutil
import numpy as np
import pytest
import soundfile as sf
from choir_splitter.audio import Cancelled, enhance, export_audio, process, run_command


def tone(hz, duration=1, rate=44100):
    return .2 * np.sin(2 * np.pi * hz * np.arange(int(duration * rate)) / rate)


def test_bass_enhancement_favors_lower_tones_preserves_timing_and_stereo():
    low, high = tone(110), tone(880)
    source = np.column_stack((low + high, low + high))
    result = enhance(source, 44100, "Bass")
    assert result.shape == source.shape
    assert np.isfinite(result).all()
    assert np.max(np.abs(result)) <= .951
    np.testing.assert_allclose(result[:, 0], result[:, 1], atol=1e-6)
    bins = np.fft.rfftfreq(len(result), 1 / 44100)
    spectrum = abs(np.fft.rfft(result[:, 0]))
    assert spectrum[np.argmin(abs(bins - 110))] > 3 * spectrum[np.argmin(abs(bins - 880))]
    assert abs(bins[np.argmax(spectrum)] - 110) < 1


@pytest.mark.parametrize("length", [1, 100, 4096, 44100])
def test_silence_and_short_clips(length):
    result = enhance(np.zeros((length, 2)), 44100, "Tenor")
    assert result.shape == (length, 2)
    assert np.isfinite(result).all()
    assert np.max(np.abs(result)) == 0


def test_invalid_audio_rejected():
    with pytest.raises(ValueError):
        enhance(np.array([float("nan")]), 44100, "Bass")
    with pytest.raises(ValueError):
        enhance(np.zeros(10), 44100, "Baritone")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_end_to_end_formats_and_cancel(tmp_path):
    original = tmp_path / "recording.wav"
    sf.write(original, np.column_stack((tone(150), tone(150))), 44100)
    output = process(original, tmp_path / "result.wav", "Tenor", "Range enhancement")
    assert sf.info(output).frames == 44100
    assert sf.info(output).subtype == "PCM_24"
    mp3 = tmp_path / "practice.mp3"
    export_audio(output, mp3)
    assert mp3.stat().st_size > 1000
    # Exercise compressed input decoding and WAV re-export.
    decoded = process(mp3, tmp_path / "again.wav", "Bass", "Range enhancement")
    assert abs(sf.info(decoded).duration - 1) < .05
    export_audio(output, tmp_path / "export.wav")
    with pytest.raises(ValueError):
        export_audio(output, output)
    cancel = Event()
    cancel.set()
    with pytest.raises(Cancelled):
        process(original, tmp_path / "cancelled.wav", "Bass", "Range enhancement", cancel=cancel)
    assert not (tmp_path / "cancelled.wav").exists()


def test_subprocess_cancel():
    import sys
    cancel = Event()
    cancel.set()
    with pytest.raises(Cancelled):
        run_command([sys.executable, "-c", "import time; time.sleep(30)"], cancel)


def test_optional_real_demucs_inference(tmp_path):
    import os
    from choir_splitter.audio import demucs_ready
    if os.environ.get("CHOIR_TEST_AI") != "1":
        pytest.skip("Set CHOIR_TEST_AI=1 after installing AI dependencies and caching weights")
    assert demucs_ready(), "Run --prepare-model explicitly before this test"
    source = tmp_path / "synthetic.wav"
    sf.write(source, np.column_stack((tone(147), tone(147))), 44100)
    output = process(source, tmp_path / "vocals.wav", "Tenor", "Demucs + range enhancement")
    samples, rate = sf.read(output, always_2d=True)
    assert rate == 44100
    assert samples.shape == (44100, 2)
    assert np.isfinite(samples).all()
    assert np.max(np.abs(samples)) <= .951
