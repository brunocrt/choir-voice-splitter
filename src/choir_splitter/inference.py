"""Isolated, strictly local HT-Demucs inference worker.

SoundFile handles PCM I/O to avoid TorchAudio codec API drift. LocalRepo prevents
network-backed repository access during inference; model preparation is separate.
"""
from __future__ import annotations
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    import numpy as np
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Choose CPU or install a compatible CUDA-enabled PyTorch build.")
    # A signature + local repo performs no remote model lookup/download.
    from fractions import Fraction
    from importlib import import_module
    from demucs.htdemucs import HTDemucs
    # Demucs checkpoints include architecture metadata. Explicitly allow only
    # the known metadata types under modern PyTorch's weights-only loader.
    with torch.serialization.safe_globals([
        HTDemucs, Fraction, np.dtype, np.dtypes.Float64DType,
        (import_module("numpy.core.multiarray").scalar, "numpy.core.multiarray.scalar"),
    ]):
        model = get_model("955717e8", repo=args.cache)
    model.eval()
    samples, rate = sf.read(args.input, dtype="float32", always_2d=True)
    if rate != model.samplerate or samples.shape[1] != model.audio_channels:
        raise ValueError("Inference input has an unexpected sample rate or channel count.")
    wav = torch.from_numpy(samples.T.copy())
    reference = wav.mean(0)
    mean, std = reference.mean(), reference.std().clamp_min(1e-8)
    wav = (wav - mean) / std
    with torch.inference_mode():
        sources = apply_model(model, wav[None], device=args.device,
                              shifts=0, split=True, overlap=.25, progress=False)[0]
    vocals = (sources[model.sources.index("vocals")] * std + mean).cpu().numpy().T
    if not np.isfinite(vocals).all():
        raise RuntimeError("Model produced invalid audio samples.")
    sf.write(args.output, vocals, rate, subtype="FLOAT")


if __name__ == "__main__":
    main()
