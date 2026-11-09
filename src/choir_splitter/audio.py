"""Audio decoding, optional pretrained vocal extraction, and transparent DSP.

Range enhancement is a spectral mask, NOT independent SATB source separation.
No inference command intentionally downloads weights. Model setup is explicit.
"""
from __future__ import annotations
from pathlib import Path
from threading import Event
from typing import Callable
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
import soundfile as sf
from scipy import signal
from .project import PARTS

class Cancelled(Exception):
    pass


def ffmpeg() -> str:
    executable = os.environ.get("CHOIR_FFMPEG") or shutil.which("ffmpeg")
    if not executable or not Path(executable).is_file():
        raise RuntimeError("FFmpeg is required. Install it and add it to PATH, or set CHOIR_FFMPEG.")
    return str(executable)


def run_command(args: list[str], cancel: Event | None = None) -> None:
    """Avoid pipe deadlocks and bound diagnostics; support cancellation of inference."""
    with tempfile.TemporaryFile() as log:
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        process = subprocess.Popen(args, stdout=log, stderr=log, stdin=subprocess.DEVNULL, **flags)
        try:
            while process.poll() is None:
                if cancel and cancel.wait(0.1):
                    raise Cancelled("Processing cancelled.")
                if cancel is None:
                    time.sleep(0.1)
            if process.returncode:
                log.seek(0, 2)
                log.seek(max(0, log.tell() - 3000))
                raise RuntimeError(log.read().decode(errors="replace").strip() or "Audio command failed.")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def model_cache() -> Path:
    torch_home = Path(os.environ.get("TORCH_HOME", Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "torch"))
    return torch_home / "hub" / "checkpoints"


def demucs_ready() -> bool:
    return importlib.util.find_spec("demucs") is not None and any(model_cache().glob("955717e8-*.th"))


def enhance(audio: np.ndarray, sample_rate: int, part: str, strength: float = 0.85,
            cancel: Event | None = None) -> np.ndarray:
    """Smooth STFT mask around a part's fundamental range and first harmonics.

    Identical masks on both channels preserve stereo phase relationships. Gain
    normalization never raises peaks beyond 0.95. No pitch/time transformation.
    """
    if part not in PARTS:
        raise ValueError("Unknown voice part.")
    if sample_rate < 8000 or not 0 <= strength <= 1:
        raise ValueError("Invalid audio settings.")
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        audio = audio[:, None]
    if audio.ndim != 2 or audio.shape[1] not in (1, 2) or not len(audio):
        raise ValueError("Expected nonempty mono or stereo audio.")
    if not np.isfinite(audio).all():
        raise ValueError("Audio contains invalid samples.")
    original_length = len(audio)
    nfft = 4096
    frequencies = np.fft.rfftfreq(nfft, 1 / sample_rate)
    low, high = PARTS[part]
    # Soft boundaries avoid ringing. Harmonics improve clarity but admit bleed.
    safe = np.maximum(frequencies, 1)
    fundamental = np.exp(-0.5 * (np.maximum(np.log2(low / safe), 0) / .28) ** 2)
    fundamental *= np.exp(-0.5 * (np.maximum(np.log2(safe / high), 0) / .28) ** 2)
    harmonic = np.exp(-0.5 * (np.log2(safe / (high * 1.5)) / .65) ** 2) * .3
    mask = (1 - strength) + strength * np.maximum(fundamental, harmonic)
    mask[frequencies < 35] = 0
    # Bound spectral working memory. Aligned overlapping context keeps the STFT
    # grid identical across chunks and avoids seams at their central boundaries.
    hop = 1024
    chunk_size = max(hop, int(sample_rate * 20) // hop * hop)
    output = np.empty_like(audio)
    for start in range(0, original_length, chunk_size):
        if cancel and cancel.is_set():
            raise Cancelled()
        stop = min(start + chunk_size, original_length)
        left, right = max(0, start - nfft), min(original_length, stop + nfft)
        block = audio[left:right]
        if len(block) < nfft:
            block = np.pad(block, ((0, nfft - len(block)), (0, 0)))
        _, _, spectrum = signal.stft(block, sample_rate, nperseg=nfft,
                                      noverlap=nfft - hop, axis=0)
        _, restored = signal.istft(spectrum * mask[:, None, None], sample_rate,
                                   nperseg=nfft, noverlap=nfft - hop,
                                   time_axis=-1, freq_axis=0)
        output[start:stop] = restored.T[start - left:stop - left]

    peak = np.max(np.abs(output))
    if peak > 0:
        # Limit gain to avoid amplifying recording noise in very quiet files.
        output *= min(0.95 / peak, 2.0)
    return output


def process(source: Path, destination: Path, part: str, mode: str,
            device: str = "cpu", cancel: Event | None = None,
            progress: Callable[[int, str], None] = lambda *_: None) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"Recording not found: {source}")
    if part not in PARTS or mode not in ("Range enhancement", "Demucs + range enhancement"):
        raise ValueError("Unknown processing settings.")
    if device not in ("cpu", "cuda"):
        raise ValueError("Unknown compute device.")
    executable = ffmpeg()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="choir-") as directory:
        work = Path(directory)
        decoded = work / "decoded.wav"
        progress(5, "Decoding recording")
        # Thirty minutes is a deliberate memory bound for this in-memory MVP.
        probe = shutil.which("ffprobe")
        if probe:
            result = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                                     "-of", "json", str(source)], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                duration = float(json.loads(result.stdout).get("format", {}).get("duration", 0))
                if duration > 1800:
                    raise ValueError("Recordings must be 30 minutes or shorter. Split this recording first.")
        run_command([executable, "-nostdin", "-v", "error", "-y", "-i", str(source),
                     "-t", "1801", "-ar", "44100", "-ac", "2", "-c:a", "pcm_f32le", str(decoded)], cancel)
        if sf.info(decoded).duration > 1800:
            raise ValueError("Recordings must be 30 minutes or shorter.")
        vocal = decoded
        if mode == "Demucs + range enhancement":
            if not demucs_ready():
                raise RuntimeError("Demucs or its cached htdemucs weights are missing. See Settings and README for one-time setup. No model was downloaded.")
            if getattr(sys, "frozen", False):
                raise RuntimeError("This packaged DSP build does not bundle Demucs. Run the Python source installation for AI processing.")
            progress(15, "Extracting vocal stem with HT-Demucs (this can take several minutes)")
            vocal = work / "vocals.wav"
            run_command([sys.executable, "-m", "choir_splitter.inference", "--input", str(decoded),
                         "--output", str(vocal), "--cache", str(model_cache()), "--device", device], cancel)
        if cancel and cancel.is_set():
            raise Cancelled()
        progress(75, f"Enhancing the {part.lower()} range")
        samples, rate = sf.read(vocal, dtype="float32", always_2d=True)
        enhanced = enhance(samples, rate, part, cancel=cancel)
        if cancel and cancel.is_set():
            raise Cancelled()
        temporary = destination.with_name(destination.stem + ".partial.wav")
        try:
            sf.write(temporary, enhanced, rate, subtype="PCM_24")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        progress(100, "Complete")
    return destination


def export_audio(source: Path, destination: Path, cancel: Event | None = None) -> None:
    destination = destination.resolve()
    if destination == source.resolve():
        raise ValueError("Choose a different export path from the working audio file.")
    if destination.suffix.lower() not in (".wav", ".mp3"):
        raise ValueError("Export supports MP3 or WAV.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=destination.parent, suffix=destination.suffix)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        codec = ["-c:a", "libmp3lame", "-b:a", "192k"] if destination.suffix.lower() == ".mp3" else ["-c:a", "pcm_s24le"]
        run_command([ffmpeg(), "-nostdin", "-v", "error", "-y", "-i", str(source), *codec, str(temporary)], cancel)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
