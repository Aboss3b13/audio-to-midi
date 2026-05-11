# Music Sheet Builder 🎵

A professional-grade Streamlit web application that intelligently converts audio recordings into sheet music, MIDI files, and isolated instrument layers. Whether you're transcribing a piano recording, separating vocals from instruments, or documenting musical ideas, Music Sheet Builder provides powerful transcription and arrangement tools.

## Overview

Music Sheet Builder is an end-to-end audio-to-notation system that combines cutting-edge pitch detection, intelligent layer separation, and interactive music editing—all in a beautiful, modern web interface.

### What It Does

1. **Audio Transcription**: Converts audio files (MP3, WAV, M4A, FLAC) or live recordings into precise MIDI and MusicXML notation
2. **Intelligent Instrument Separation**: Automatically detects and separates multiple instruments using advanced clustering or stem-guided analysis
3. **Sheet Music Generation**: Creates professional-grade MusicXML output that can be imported into notation software (Finale, Sibelius, MuseScore, etc.)
4. **Interactive Arrangement**: Reassign instruments, adjust note timing, control sustain pedal, transpose, and customize each layer
5. **High-Quality Playback**: Renders arranged compositions using quality SoundFont libraries with realistic instrument sounds

## Key Features

### 📥 Audio Input & Recording
- **Multi-format Support**: Import MP3, WAV, M4A, FLAC files or record directly in your browser
- **Flexible Source Handling**: Process files from disk or capture fresh recordings
- **Automatic Normalization**: Audio is automatically normalized for optimal transcription quality

### 🎼 Intelligent Transcription
- **Dual Transcription Modes**:
  - **Clustering Mode**: Automatic note clustering and layer detection from full-mix transcription
  - **Replica Mode** (Multi-Pass Stem-Guided): Decomposes audio into harmonic/percussive stems and transcribes each separately for better separation
- **Basic-Pitch Integration**: Industry-standard pitch detection with adjustable onset and frame thresholds
- **Sustain Pedal Support**: Two-pass transcription (balanced + sustain-biased) for accurate note duration capture
- **Note Smoothing**: Advanced filtering to reduce stutter, merge pitch flickers, and consolidate split notes

### 🎹 Automatic Layer Detection
- **K-Means Clustering**: Segments detected notes by pitch range, density, and temporal characteristics
- **Intelligent Labeling**: Automatically classifies layers as Bass, Lead, Harmony, Strings/Pads, etc.
- **Confidence Scoring**: Each layer receives a confidence metric based on spectral and temporal features
- **Adjustable Layer Count**: Override automatic detection with a target layer count for custom separation

### 🎨 Interactive Arrangement Interface
- **Per-Layer Customization**:
  - Select from 100+ GM (General MIDI) instruments
  - Transpose ±12 semitones per layer
  - Scale velocity (note volume)
  - Adjust timing (shift note onsets)
  - Toggle sustain pedal per layer
  - Enable/disable layers to exclude from output
- **Real-Time Preview**: Immediately preview changes with high-quality SoundFont rendering
- **Visual Score Display**: View sheet music inline with Verovio rendering

### 📊 Output Formats
- **MIDI Files**: Full-mix and individual layer MIDI with GM instrument assignments
- **MusicXML**: Sheet-ready notation for professional music notation software
- **WAV Audio**: High-quality rendered audio from arranged composition
- **Organized Project Structure**: All outputs saved with timestamp organization for easy project management

### 🎛️ Advanced Tuning Controls
Fine-grained parameters for transcription quality:
- **Onset Threshold** (0.0–1.0): Sensitivity to note attack detection (default: 0.58)
- **Frame Threshold** (0.0–1.0): Pitch confidence for sustained notes (default: 0.24)
- **Minimum Note Length** (ms): Shortest note duration to capture (default: 170ms)
- **Merge Gap** (ms): Distance to merge adjacent same-pitch notes (default: 120ms)
- **Legato Extension** (ms): Extend notes to reduce gaps between legato passages (default: 65ms)
- **Flicker Merge Gap** (ms): Collapse tiny pitch oscillations (default: 45ms)

### 💾 Project Management
- **Timestamped Runs**: Each transcription saved with unique timestamp directory
- **Layered Exports**: Individual layer MIDI and MusicXML files alongside full mix
- **Persistent Session**: In-browser state management for uninterrupted workflow

## How It Works

### Transcription Pipeline

```
Audio Input
    ↓
[Load & Normalize Audio]
    ↓
Dual Path:
├─ Clustering Mode:
│  ├─ Full-mix transcription (Basic-Pitch)
│  ├─ Two-pass fusion (balanced + sustain)
│  ├─ Note post-processing (merge, flicker reduction, legato)
│  └─ K-means clustering on features → Layer separation
│
└─ Replica Mode:
   ├─ HPSS decomposition → 4 frequency-band stems
   ├─ Per-stem transcription with frequency bounds
   └─ Stem-guided layer organization
    ↓
[Generate MIDI & MusicXML]
    ↓
[Render Preview Audio via SoundFont]
    ↓
[Interactive Editor & Visualization]
    ↓
Outputs: MIDI, MusicXML, WAV, Layer Files
```

### Layer Detection Algorithm

Detected notes are represented as 4-D feature vectors:
- **Pitch** (0–127 normalized)
- **Time** (start position in piece)
- **Duration** (note length)
- **Velocity** (volume)

K-means clustering groups notes into coherent instruments. Each cluster is profiled:
- **Mean Pitch**: Determines if bass, harmony, or lead
- **Note Density**: High density → plucked/percussive; low density → sustained
- **Duration Profile**: Long sustained notes → strings/pads; short → lead/melody

The algorithm then assigns each cluster to a likely General MIDI instrument and generates isolated MIDI/MusicXML for that layer.

## Project Structure

```
audio-to-midi/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── assets/
│   └── soundfonts/
│       └── MuseScore_General.sf3  # Default SoundFont for rendering
├── src/music_identifier/           # Core transcription package
│   ├── __init__.py                # Package exports
│   ├── pipeline.py                # Audio analysis & transcription orchestration
│   ├── instruments.py             # General MIDI instrument definitions
│   ├── playback.py                # Arrangement & SoundFont rendering
│   └── soundfont.py               # SoundFont management
└── runs/                          # Generated outputs (timestamped directories)
    └── YYYYMMDD_HHMMSS_ffffff/
        ├── full_mix.mid
        ├── full_mix.musicxml
        ├── full_mix_layered.mid
        ├── full_mix_layered.musicxml
        ├── layer_01.mid
        ├── layer_01.musicxml
        ├── layer_02.mid
        ├── layer_02.musicxml
        └── [additional layer files...]
```

## Installation

### Requirements
- Python 3.10 to 3.12 (3.11 recommended)
- ~2GB available disk space (for SoundFont + dependencies)

### Setup

```powershell
# Clone the repository
git clone https://github.com/Aboss3b13/audio-to-midi.git
cd audio-to-midi

# Create virtual environment
py -3.11 -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

The app will automatically download the MuseScore General SoundFont on first run.

### Dependencies

Core libraries used in this project:
- **streamlit** (UI framework)
- **basic-pitch** (pitch detection)
- **music21** (MIDI/MusicXML manipulation)
- **librosa** (audio processing)
- **pretty_midi** (MIDI generation)
- **verovio** (sheet music rendering)
- **pyfluidsynth** (audio synthesis)
- **soundfile** (audio I/O)
- **numpy, scipy, pandas** (data processing)
```

## Quick Start

### 1. Launch the Application
```powershell
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`.

### 2. Prepare Your Audio
- Click **Upload Audio** to select an MP3, WAV, M4A, or FLAC file, OR
- Click **Record** to capture audio directly in your browser

### 3. Configure Transcription
In the left sidebar, configure transcription parameters:
- **Transcription Mode**: Choose between:
  - *Clustering*: Fast, works well for simple arrangements
  - *Replica* (recommended): Uses stem-guided multi-pass for better separation
- **Tune Advanced Parameters** (optional):
  - Adjust onset/frame thresholds for different audio qualities
  - Control note merging behavior
  - Fine-tune sustain detection
- **Layer Detection**:
  - Enable/disable automatic layer detection
  - Override with custom layer count
  - Set minimum layer energy ratio

### 4. Transcribe
Click the **"Transcribe Audio"** button. This may take 30 seconds to several minutes depending on:
- Audio length
- Transcription mode (Replica mode is slower but more accurate)
- Your system performance

### 5. Arrange & Customize
Once transcription completes:
- View detected layers in the **Instrument Layers** panel
- For each layer:
  - **Select Instrument**: Choose from 100+ General MIDI instruments
  - **Transpose**: Shift up/down by semitones
  - **Velocity**: Scale note volumes
  - **Timing**: Adjust note onset times
  - **Sustain Pedal**: Toggle CC64 support
  - **Enable/Disable**: Exclude layers from output
- Click **"Render Preview"** to hear your arrangement

### 6. Export & Visualize
- **Sheet View**: See score rendered in real-time
- **Download Options**:
  - Full-mix MIDI
  - Full-mix MusicXML (for notation software)
  - Individual layer MIDI files
  - High-quality WAV rendering

## Usage Scenarios

### Transcribing Piano Recordings
1. Upload a piano recording
2. Enable **Replica Mode** for better note separation
3. Adjust **Onset Threshold** down to 0.50 if notes are being missed
4. Export as MusicXML to MuseScore for final cleanup
5. Add dynamics, articulations, and tempo markings manually

### Separating Multi-Instrument Pieces
1. Use **Replica Mode** with custom layer count
2. Adjust **Minimum Layer Energy Ratio** if small layers are being skipped
3. Manually assign instruments in the UI
4. Use **Transpose** to fix layers that detected an octave too high/low
5. Export individual layer MIDI files for use in DAW

### Documentation & Analysis
1. Record musical ideas on acoustic instruments
2. Transcribe quickly with default settings
3. Export MusicXML for archiving
4. Use for reference when composing/arranging

### AI Model Training
1. Generate synthetic training data: transcribe → arrange → render
2. Export paired (audio, MIDI) files from multiple runs
3. Use as augmented training set

## SoundFont Configuration

### Automatic Setup
The app automatically downloads **MuseScore General 3.9** (~160MB) on first launch. This is a high-quality free soundfont covering all 128 GM instruments.

### Custom SoundFonts
To use a different SoundFont:
1. In the sidebar, go to **SoundFont Settings**
2. Toggle **"Use Custom SoundFont"**
3. Upload a `.sf2` or `.sf3` file from your computer
4. Click **"Render Preview"** to apply

### System Requirements for Synthesis
- **Linux**: `apt-get install fluidsynth`
- **macOS**: `brew install fluid-synth`
- **Windows**: Pre-built binaries included with most Python installations

## Sheet Music Viewer

The in-app sheet viewer uses **Verovio** to render MusicXML in your browser:
- **Real-time Updates**: Sheet updates immediately when you change arrangements
- **Zoom & Navigation**: Use browser zoom or Verovio controls
- **Two Display Modes**:
  - *Arranged Score*: Shows your final arrangement with instrument reassignments
  - *Detected Score*: Shows raw note clustering result
- **Error Handling**: If MusicXML parsing fails, the app displays diagnostics and keeps the download available

## Advanced Topics

### Note Post-Processing Pipeline

The transcription pipeline applies sophisticated note smoothing:

1. **Pitch Flicker Reduction**: Consecutive notes differing by 1 semitone within 45ms are collapsed into a single sustained note
2. **Same-Pitch Merging**: Adjacent notes of identical pitch are merged if gap ≤ merge_gap_ms
3. **Legato Extension**: Note ends are extended toward next note onset (up to 65ms) to smooth legato passages
4. **Sustain Fusion**: Two-pass transcription is fused—sustain pass extends durations of notes from primary pass
5. **Minimum Duration Filtering**: Notes shorter than min_output_note_length_ms are dropped

### Layer Clustering Algorithm

Layer detection uses **K-means clustering** on note feature vectors:

**Features per note:**
- Pitch (0–127, normalized to 0–1)
- Start time (position as % of total duration)
- Duration (log-scaled: min(duration / 2.5, 1.0))
- Velocity (0–127, normalized to 0–1)

**Layer Classification:**
After clustering, each cluster is profiled:
```
if mean_pitch ≤ 47 (MIDI C2):
  → Bass Instrument (GM 33: Finger Bass)
elif density > 5.8 notes/sec AND duration < 0.24s:
  → Plucked/Percussive (GM 24: Nylon Guitar)
elif mean_pitch ≥ 74 (MIDI D5) AND duration ≥ 0.34s:
  → Lead Melody (GM 40: Violin)
elif duration ≥ 0.85s:
  → Strings/Pad (GM 48: String Ensemble)
else:
  → Harmony Instrument (GM 0: Piano)
```

### Replica Mode (Stem-Guided) Pipeline

When enabled, Replica Mode provides superior instrument separation:

1. **HPSS Decomposition**: Uses **Harmonic-Percussive Source Separation** to split audio
2. **Frequency Binning**: Creates specialized stems:
   - Bass Stem: 28–220 Hz → Bass instruments
   - Harmony Stem: 220–2000 Hz → Piano, guitars, chords
   - Lead Stem: 2000–8000 Hz → Vocals, leads, solos
   - Percussive Stem: Transients and drums
3. **Per-Stem Transcription**: Each stem is transcribed independently with frequency bounds applied
4. **Stem-Aware Layer Assignment**: Layers organized by which stem they originated from

This approach significantly reduces note conflicts and improves separation quality for complex mixes.

## Accuracy & Limitations

### What It Does Well
- ✅ **Solo Instruments**: Single melody lines (voice, flute, violin, etc.) transcribe accurately
- ✅ **Simple Arrangements**: 2–3 instrument pieces with clear separation
- ✅ **Monophonic Music**: Music with one note playing at a time
- ✅ **Clean Recordings**: High-quality, isolated recordings
- ✅ **Steady Tempo**: Music with consistent tempo

### Known Limitations
- ❌ **Dense Polyphonic Mix**: 4+ simultaneous notes from different pitch ranges can produce missing/incorrect notes
- ❌ **Chords**: Harmonies are transcribed as individual notes but may not always capture exact voicing
- ❌ **Drums/Percussion**: Rhythm detected, but articulation (short hits) may be over-shortened
- ❌ **Extreme Dynamics**: Very quiet passages may be missed; very loud may clip
- ❌ **Heavy Reverb/Delay**: Long tails can cause note duration inflation
- ❌ **Polyphonic Monophonic Detection**: The system assumes monophonic input; polyphonic sources will be treated as layered monophonic

### Best Practices for Better Results

| Issue | Solution |
|-------|----------|
| Notes are being missed | Lower **Onset Threshold** to 0.45–0.50, or increase **Frame Threshold** to 0.28–0.32 |
| Too many spurious notes | Raise **Onset Threshold** to 0.65–0.70, or reduce **Frame Threshold** to 0.18–0.22 |
| Notes are too short | Increase **Minimum Note Length** or **Legato Extension** |
| Pitch flicker | Increase **Flicker Merge Gap** or reduce **Frame Threshold** |
| Sustain pedal not captured | Enable **Sustain Boost** (already enabled by default in Replica mode) |
| Layers not separating well | Switch to **Replica Mode**, or increase **Target Layer Count** |

### Post-Processing Workflow

For publication-quality transcriptions:
1. Export MusicXML from Music Sheet Builder
2. Open in **MuseScore**, **Finale**, or **Dorico**
3. Manually correct:
   - Wrong accidentals (often F♯ vs G♭)
   - Missing rests in sparse regions
   - Beaming across bar lines
   - Dynamics and articulation
   - Tempo markings
4. Re-export with your notation software's polishing

## Troubleshooting

### "ModuleNotFoundError: No module named 'basic_pitch'"
```powershell
pip install --upgrade basic-pitch
```

### "SoundFont file not found"
- Check that `assets/soundfonts/` exists
- The app will auto-download if missing; it may take a few minutes
- Or manually upload a `.sf2`/`.sf3` file in the SoundFont Settings panel

### "Verovio rendering failed" or blank sheet display
- MusicXML may have encoding issues; check the diagnostics panel
- Export the raw MusicXML file and open in **MuseScore** to validate
- Sometimes line break or page break markup causes issues—try importing into notation software

### Transcription is very slow
- **Replica Mode** is slower but more accurate; for quick results, disable it
- Reduce audio duration (transcribe just a section, not full 5-minute songs)
- Use a more powerful machine; GPU support not currently implemented

### Output MIDI has the wrong tempo
- MIDI files are generated at 120 BPM by default
- Adjust tempo in your DAW/notation software after importing
- The app does not auto-detect tempo; manual adjustment is needed

### Layers are not separating as expected
- Increase **Target Layer Count** if too few layers are being detected
- Lower **Minimum Layer Energy Ratio** if small layers are being skipped
- Switch to **Replica Mode** for complex pieces
- Some pieces (dense chords, fast runs) inherently difficult to separate

## Architecture & Code Overview

### Core Modules

#### `pipeline.py`
Orchestrates audio analysis:
- `analyze_audio()`: Main entry point; runs transcription and layer detection
- `_run_predict_pass()`: Calls Basic-Pitch model for pitch detection
- `_post_process_midi_notes()`: Applies smoothing and merging filters
- `_build_instrument_layers_from_midi()`: K-means clustering and layer assignment
- `_build_layers_from_replica_stems()`: Stem-guided multi-pass transcription
- `_extract_replica_stems()`: HPSS decomposition and frequency binning

#### `playback.py`
Handles arrangement and rendering:
- `apply_instrument_map_and_render_preview()`: Applies instrument/transpose/velocity changes and renders WAV
- `list_midi_tracks()`: Extracts layer info from MIDI for UI

#### `instruments.py`
Defines all 128 General MIDI instruments:
- `INSTRUMENT_PRESETS`: Dict mapping instrument names to GM program numbers
- Used for dropdown UI and MIDI file generation

#### `soundfont.py`
Manages SoundFont lifecycle:
- `ensure_default_soundfont()`: Auto-downloads MuseScore General if missing
- `DEFAULT_SOUNDFONT_NAME`: Path to default or custom SoundFont

#### `app.py`
Main Streamlit UI application:
- Handles audio upload/recording
- Manages transcription state
- Renders arrangement controls
- Displays sheet music and metrics

## Contributing

Contributions are welcome! Areas for improvement:
- 🎼 Polyphonic pitch detection (handle multiple simultaneous notes)
- ⚡ GPU acceleration for Basic-Pitch
- 🎨 Better layer separation heuristics
- 📊 Performance profiling and optimization
- 🌍 Multi-language support for UI
- 🔧 VST plugin wrapper for DAW integration
- 📱 Web deployment (currently local-only)

To contribute:
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make changes and test thoroughly
4. Submit a pull request

## License

[Add your chosen license here, e.g., MIT, GPL-3.0, etc.]

## Authors

Created with ❤️ for musicians, composers, and music technologists.

## Support & Feedback

- 🐛 Report issues on GitHub Issues
- 💡 Suggest features in GitHub Discussions
- 📧 Contact: [your contact info]

---

**Enjoy transforming your audio into beautiful sheet music! 🎵**
