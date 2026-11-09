# Choir Voice Splitter

An offline Python 3.12+ desktop rehearsal studio, implementing the practical first stage of the supplied choir-splitting specification.

**This is a working rehearsal-tool prototype, not a validated SATB separator.** It enhances a selected vocal register. Optional HT-Demucs can extract a vocal stem before enhancement, but cannot assign simultaneously singing voices to Tenor/Bass. No pretrained SATB model is supplied, and no choir-quality success claim has been established.

## Run on Windows or macOS

Install Python 3.12 and [FFmpeg](https://ffmpeg.org/download.html), including `ffprobe`, and put both executables on PATH. `CHOIR_FFMPEG` can point to a specific FFmpeg executable. On macOS with Homebrew, use `brew install ffmpeg`. On Windows, use an FFmpeg distribution linked from the official download page and add its `bin` directory to PATH.

From this folder:

```sh
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or macOS:

```sh
source .venv/bin/activate
```

Then:

```sh
python -m pip install -e .
python -m choir_splitter
```

The range-enhancement mode needs no model and works offline immediately after installation. MP3, WAV, M4A, AAC, OGG/OPUS (including common WhatsApp exports), FLAC and WMA are decoded through FFmpeg. An audio file must be exported from WhatsApp first; the app does not connect to WhatsApp or decrypt message databases. Supported codecs depend on the installed FFmpeg build.

## Optional AI vocal extraction

In the same virtual environment, install a matching PyTorch/TorchAudio pair for your platform from [PyTorch](https://pytorch.org/get-started/locally/), then:

```sh
python -m pip install -e ".[ai]"
python -m choir_splitter --prepare-model
```

The explicit preparation command requires internet and downloads HT-Demucs weights. It can also initialize their dependencies. After preparation, select **Demucs + range enhancement**. The application checks that Demucs and the standard HT-Demucs checkpoint are cached before running inference. The worker loads its signature from a strictly local model repository; it has no remote model fallback. It never calls the model-preparation command during processing. For an air-gapped installation, install dependencies and prepare weights on a staging machine, then transfer the virtual environment/installers and the Torch checkpoint cache in a manner compatible with the target OS/architecture. `TORCH_HOME` relocates the model cache.

CPU inference is supported. NVIDIA CUDA is optional on Windows/Linux with a compatible GPU and PyTorch installation. macOS uses CPU in this version; MPS has not been implemented. CUDA has not been validated on the development host.

## Model-download certificate errors on macOS

If `--prepare-model` fails with `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`, Python cannot verify the HTTPS certificate chain. With a python.org macOS installation, run its certificate setup script (use your installed Python version):

```sh
open "/Applications/Python 3.14/Install Certificates.command"
```

Wait for that script to finish successfully, then retry in the activated virtual environment:

```sh
python -m choir_splitter --prepare-model
```

If that script is absent, use the certificate setup instructions for your Python distribution. On a company network with HTTPS inspection, ask IT for the trusted CA bundle and set `SSL_CERT_FILE` to its path before retrying. A public CA bundle alone may not include your company's CA. Keep TLS verification enabled.

Python 3.12 was used for development validation. The supplied macOS error log uses Python 3.14; this certificate failure occurs before inference and does not by itself indicate a Python/Demucs compatibility problem.

## Use

1. Add or drag in recordings. Duplicates are skipped.
2. Select one or several rows, then choose their voice part and method. Settings changes apply to selected rows; new imports inherit the displayed settings. Tenor and Bass are the primary choices; Alto and Soprano use the same experimental DSP method.
3. Click **Enhance all recordings**. Files process sequentially on a background thread; a failure does not stop the remaining batch. Cancel keeps completed results.
4. Select a row and switch between **Original recording** and **Enhanced voice**. Scrub or adjust playback speed. Speed changes may affect pitch on some multimedia backends; exported audio always retains original timing and pitch.
5. **Export selected…** saves one recording as MP3 (192 kbps) or 24-bit WAV. Selecting multiple completed rows exports MP3 files into a chosen folder with distinct names.
6. Save a `.choir` project. Keep the accompanying `.assets` folder: it holds generated WAV results. Original recordings remain external references, stored relative to the project when possible. Keep originals in the same relative location when moving a project. Reopen and re-export without inference. Missing originals are flagged; available saved results can still be previewed/exported.

Recordings are limited to 30 minutes. DSP processes the spectrum in bounded chunks, but input/output arrays remain in memory. Results are retained in the OS application-data directory and copied into project assets on save. This MVP does not automatically delete old working results; after exporting/saving and closing the app, unused working WAVs can be removed manually from the `results` subfolder in its application-data directory. The app displays failures in the status bar and track tooltip.

## Tests

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
```

On a headless Linux machine:

```sh
QT_QPA_PLATFORM=offscreen QT_AUDIO_BACKEND=pulseaudio python -m pytest -q
```

Tests cover spectral behavior and unchanged sample count, short clips/silence, format round trips through FFmpeg, cancellation, project recovery, and Qt controls. See `docs/VALIDATION.md` for the actual checks run. Synthetic signals validate implementation, not choir separation quality.

## Desktop packaging

Build on each target operating system; PyInstaller does not cross-compile Windows/macOS installers:

```sh
python -m pip install -e ".[dev]"
pyinstaller --noconfirm --clean --windowed --onedir --name ChoirVoiceSplitter --paths src run.py
```

This is a **DSP-only packaging recipe**. The frozen app deliberately rejects Demucs mode: optional inference launches `sys.executable -m choir_splitter.inference`, which requires the source/Python installation. A distributable AI edition needs a separate bundled inference executable or in-process inference integration; do not label this packaging recipe AI-complete.

FFmpeg is an external runtime dependency. For a distributable release, bundle an appropriate licensed build, configure its path, and fulfill its license obligations. Review LGPL requirements for PySide6, PyInstaller notices, PyTorch/Demucs dependencies, and weight licensing. Sign/notarize native artifacts. Native Windows/macOS packaging and audio-device behavior require validation on those systems before release.

## Design and next steps

`docs/ARCHITECTURE.md` contains the architecture recommendation, model comparisons, all five requested Mermaid diagrams, deployment constraints, risks, estimates, and feasibility conclusion. `docs/ROADMAP.md` describes the path to a validated product.
