# Validation record

Development environment: Linux x86_64, Python 3.12.14; NumPy 2.3.5, SciPy 1.17.0, SoundFile 0.14.0, PySide6 6.12.0, pytest 9.2.0, Demucs 4.0.1, PyTorch 2.15.0+cpu, TorchAudio 2.11.1+cpu. FFmpeg/FFprobe are system dependencies.

## Checks performed

- Full suite with optional real pretrained inference enabled: **17 passed**. The host's inherited pytest plugins emit a deprecation warning unrelated to application behavior.
- Real HT-Demucs checkpoint downloaded explicitly with `--prepare-model`; actual CPU inference completed on a one-second synthetic stereo tone. Output was finite 44.1 kHz stereo, exactly 44,100 frames and 24-bit WAV. This checks integration, not choir quality.
- Full suite run with HTTP/HTTPS/ALL proxy variables set to an unreachable loopback port, using cached weights. This supports the no-download inference design; it is not a full air-gap/network-namespace certification.
- DSP: low-range emphasis, unchanged pitch peak and frame count, stereo channel consistency, bounded output, invalid input, silence and tiny clips.
- FFmpeg: decode WAV and MP3, process, export MP3 and WAV, reject same-file export, cancel without committing partial result.
- Projects: atomic save and relative references, reopening, missing originals/results, schema rejection, unsafe track ID rejection.
- Desktop: actual Qt widgets, duplicate import, per-row settings, stale-result invalidation, multi-row settings persistence, background two-file processing, portable result assets surviving working-cache deletion.
- Actual Qt window rendered and captured as `desktop-preview.png`, with clearly named synthetic demonstration files. It was visually inspected for layout/clipping. No real choir recording was supplied.

## Running the equivalent integration suite

After installing base/dev/AI dependencies and preparing weights explicitly:

```sh
CHOIR_TEST_AI=1 TORCH_HOME=/path/to/prepared/torch \
OMP_NUM_THREADS=2 QT_QPA_PLATFORM=offscreen QT_AUDIO_BACKEND=pulseaudio \
python -m pytest -q
```

Set `XDG_DATA_HOME`, `XDG_CONFIG_HOME` and `XDG_CACHE_HOME` to writable scratch directories if the test host has a read-only home directory. On this host Qt's default PipeWire backend crashed because its runtime configuration was missing. Selecting PulseAudio allowed widget testing; the host has no connected audio output, so **audible headphone playback was not validated**. This environment choice is not forced on Windows/macOS users.

## Not yet validated

- Practical choir-part separation or listening quality; no real choir corpus or human listening panel was available.
- Native Windows/macOS installation, packaging, codecs, device playback or signing/notarization.
- CUDA inference, long-track memory/runtime ceilings, MPS, or pitch preservation during slowed preview.
- Frozen AI distribution. The current frozen-build recipe intentionally supports only DSP mode.

These remain explicit release gates. The source application and tests do not establish production readiness or reliable isolated SATB outputs.
