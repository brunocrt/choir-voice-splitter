# Choir Voice Splitter - Product Requirements Document (PRD) and Software Architecture Specification

## Objective

Design a desktop software application that enables choir singers to isolate specific choir voice parts from a mixed choir recording for rehearsal and practice purposes.

The primary goal is to allow a user to upload a choir recording containing multiple singers and generate a new audio file that isolates a selected voice part.

Version 1 should prioritize:

- Tenor
- Bass

The architecture must remain extensible to support:

- Soprano
- Alto
- Tenor
- Bass (SATB)

## Business Context

Church choirs frequently distribute rehearsal recordings through WhatsApp, MP3 files, or other mobile messaging platforms.

These recordings typically contain:

- Multiple choir voices singing simultaneously
- Piano accompaniment
- Variable recording quality
- Compressed audio formats

Many singers struggle to identify and learn their own musical line from the full choir recording.

The application should help users isolate their voice section and hear it independently for rehearsal and learning purposes.

## Target Users

- Church choir singers
- Community choir members
- Vocal students
- Choir directors
- Music educators

## Core User Story

As a choir singer,

I want to upload a choir recording,

and select my voice part,

so that I can hear only my own section and practice effectively.

## Scope

### Inputs

Support:

- MP3
- WAV
- M4A
- AAC
- WhatsApp audio recordings

### Voice Selection

Allow selection of:

- Soprano
- Alto
- Tenor
- Bass

Version 1 should optimize for:

- Tenor
- Bass

### Outputs

Generate:

- Isolated voice track
- MP3 export
- Optional WAV export
- Audio preview within the application

### Batch Processing

Support multiple-file processing.

### Project Management

Allow users to:

- Save projects
- Re-open projects
- Re-export results

## Quality Goal

Target: **Good amateur choir practice quality**.

The output should:

- Make the selected voice line intelligible
- Preserve pitch accuracy
- Preserve timing and rhythm
- Minimize audio artifacts
- Be suitable for headphone practice and rehearsal

The goal is not studio-quality source separation but a practical choir-learning tool.

## Technical Constraints

- Python 3.12+
- Desktop application
- Windows support
- macOS support
- Local/offline operation
- Open-source technologies preferred
- Optional NVIDIA CUDA acceleration
- CPU-only mode supported

## Required Technical Research

### Source Separation Models

- HT-Demucs
- Demucs
- MDX-Net
- Ultimate Vocal Remover (UVR)
- Open-Unmix
- Spleeter
- Band Split RNN
- Conv-TasNet
- Other relevant state-of-the-art open-source models

### Audio Libraries

- Librosa
- TorchAudio
- FFmpeg
- SciPy
- SoundFile
- Pydub

### Machine Learning Frameworks

- PyTorch
- TensorFlow
- SpeechBrain
- Asteroid
- Pyannote
- NVIDIA NeMo
- Whisper

## Technical Evaluation

### Approach A: Frequency-Based Filtering

Use spectral analysis and frequency ranges associated with SATB voices.

Evaluate:

- Accuracy
- Complexity
- Limitations

### Approach B: Vocal Stem Extraction + Voice Classification

Separate vocals from accompaniment and classify vocal regions into SATB ranges.

Evaluate:

- Feasibility
- Accuracy
- Processing cost

### Approach C: Speaker Clustering and Voice-Part Identification

Use embeddings and clustering techniques to separate choir sections.

Evaluate:

- Practicality
- Expected performance

### Approach D: Deep Learning SATB Separation

Use modern source separation models and voice classification pipelines.

Evaluate:

- Quality potential
- Implementation complexity

### Approach E: Future Custom Choir Models

Discuss only as a future roadmap item.

Do not require custom training for Version 1.

## Architecture Deliverables

### Product Vision

Include:

- Goals
- Scope
- Constraints
- Success metrics

### System Architecture

Provide:

- High-level architecture
- Main components
- Dependencies
- Processing flow

### AI Architecture

Describe:

- Recommended pre-trained model stack
- Processing sequence
- Inference workflow
- Resource requirements

### Desktop Application Architecture

Compare:

- PyQt6
- PySide6
- Electron + Python Backend
- Tauri + Python Backend

Recommend the best choice and justify the decision.

### Deployment Architecture

Cover:

- Local installation
- Packaging
- GPU support
- Offline operation
- Cross-platform distribution

## Required Diagrams

Provide:

- Use Case Diagram
- Component Diagram
- Data Flow Diagram
- Processing Pipeline Diagram
- Sequence Diagram

Use Mermaid syntax whenever possible.

## Risk Assessment

Analyze:

- SATB overlap challenges
- Polyphonic singing complexity
- Similar vocal timbres
- Choir blending effects
- Recording quality issues
- Piano accompaniment interference
- WhatsApp compression artifacts
- Computational requirements

## Version 1 Recommendation

Recommend the single best architecture for implementation today.

Include:

### Recommended Technology Stack

- Programming language
- UI framework
- Audio libraries
- AI frameworks
- Source-separation model

### Recommended Processing Pipeline

Describe each stage from upload to export.

### Performance Expectations

Estimate:

- Processing speed
- Typical hardware requirements
- Accuracy expectations

### Development Estimate

Provide:

- Complexity assessment
- Major milestones
- Technical risks

## Explicit Requirement

The recommendation must prioritize:

1. Pre-trained open-source models.
2. Offline execution.
3. Local desktop deployment.
4. Good amateur choir rehearsal quality.
5. Practical implementation feasibility.

## Final Conclusion

Answer the following question:

**Can current open-source AI technology realistically isolate Tenor and Bass voices from typical church choir recordings well enough to create a useful rehearsal tool?**

Provide:

- What is realistically achievable today
- Expected output quality
- Current technical limitations
- Recommended implementation approach
- Probability of success for a practical choir practice application

The final document should be written from the perspective of an experienced Audio DSP Engineer, Machine Learning Architect, and Software Architect and should contain concrete technical recommendations rather than generic descriptions.
