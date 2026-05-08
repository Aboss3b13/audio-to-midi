# Music Sheet Builder

A Streamlit app that takes recorded audio or uploaded music files and generates:

- `MIDI` transcription
- `MusicXML` sheet-ready output
- estimated instrument layers (from note clustering)
- post-transcription instrument reassignment with SoundFont rendering
- optional sustain pedal (`CC64`) rendering toggle

## Features

- Upload audio (`mp3`, `wav`, `m4a`, `flac`) or record directly in-browser.
- Automatic transcription to full-mix `MIDI` and `MusicXML`.
- Optional replica mode with stem-guided multi-pass transcription.
- Instrument layer estimation from transcription notes.
- Adjustable target layer count for better separation.
- Advanced note-smoothing controls to reduce stutter and merge split sustained notes.
- Multi-pass transcription fusion (balanced + sustain-biased pass) for better duration capture.
- Optional layer-level exports.
- Instrument selection per MIDI track after score generation.
- Per-layer creative controls: transpose, velocity scaling, timing shift, and pedal toggle.
- Per-layer enable/disable so removed tracks are truly excluded from rendered outputs.
- High-quality `WAV` rendering via SoundFont (free auto-download or custom `.sf2/.sf3`).
- In-app sheet display with `verovio` (arranged score or detected score).

## Project Structure

```text
app.py
requirements.txt
src/music_identifier/
  __init__.py
  instruments.py
  pipeline.py
  playback.py
  soundfont.py
assets/soundfonts/
  MuseScore_General.sf3
runs/  # generated at runtime
```

## Install

Recommended Python version: `3.10` to `3.12`.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
streamlit run app.py
```

## SoundFont Setup

- The app can automatically download a high-quality free SoundFont: `MuseScore_General.sf3`.
- You can also upload your own `.sf2` or `.sf3` file in the sidebar.
- For SoundFont rendering, install FluidSynth on your system and ensure it is available in your environment.

## Sheet Viewer

- In-app sheet rendering uses `verovio`.
- If a score cannot be parsed, the app shows diagnostics in a collapsible panel and keeps MusicXML download available.

## Notes on Accuracy

- This app uses `basic-pitch` for transcription. It works well for many cases, but dense mixes can still produce wrong or missing notes.
- Layer detection is heuristic-based instrument estimation, not guaranteed true source-separation stems.
- Use the generated `MusicXML` in notation software (MuseScore, Dorico, Sibelius) for final manual cleanup if needed.
