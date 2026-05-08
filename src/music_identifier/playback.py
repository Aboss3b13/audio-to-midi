"""MIDI instrument remapping and SoundFont rendering."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf
from music21 import converter

from .instruments import INSTRUMENT_PRESETS


def list_midi_tracks(midi_path: Path) -> list[dict[str, str | int]]:
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    tracks: list[dict[str, str | int]] = []
    for idx, instrument in enumerate(midi.instruments):
        tracks.append(
            {
                "track_index": idx,
                "name": instrument.name or pretty_midi.program_to_instrument_name(instrument.program),
                "program": instrument.program,
                "is_drum": int(instrument.is_drum),
                "note_count": len(instrument.notes),
            }
        )
    return tracks


def _set_global_sustain_pedal(midi: pretty_midi.PrettyMIDI, enabled: bool) -> None:
    end_time = float(midi.get_end_time())
    pedal_off_time = max(0.0, end_time - 0.02)

    for instrument in midi.instruments:
        if instrument.is_drum:
            continue

        instrument.control_changes = [cc for cc in instrument.control_changes if cc.number != 64]
        if not enabled:
            continue

        instrument.control_changes.extend(
            [
                pretty_midi.ControlChange(number=64, value=127, time=0.0),
                pretty_midi.ControlChange(number=64, value=0, time=pedal_off_time),
            ]
        )
        instrument.control_changes.sort(key=lambda cc: cc.time)


def _render_with_soundfont(
    midi: pretty_midi.PrettyMIDI,
    soundfont_path: Path,
    preview_wav_path: Path,
    sample_rate: int = 44100,
) -> Path:
    try:
        audio = midi.fluidsynth(fs=sample_rate, sf2_path=str(soundfont_path))
    except Exception as exc:
        raise RuntimeError(
            "SoundFont rendering failed. Install FluidSynth and pyfluidsynth, then try again."
        ) from exc

    peak = float(np.max(np.abs(audio)))
    if peak > 1e-6:
        audio = 0.95 * (audio / peak)

    sf.write(str(preview_wav_path), audio.astype(np.float32), sample_rate)
    return preview_wav_path


def apply_instrument_map_and_render_preview(
    source_midi_path: Path,
    track_to_preset_name: dict[int, str],
    out_midi_path: Path,
    out_musicxml_path: Path,
    out_preview_wav_path: Path,
    soundfont_path: Path,
    enable_sustain_pedal: bool,
    track_enabled: dict[int, bool] | None = None,
    track_to_semitone_shift: dict[int, int] | None = None,
    track_to_velocity_scale: dict[int, float] | None = None,
    track_to_timing_shift_ms: dict[int, int] | None = None,
) -> tuple[Path, Path, Path]:
    midi = pretty_midi.PrettyMIDI(str(source_midi_path))

    enabled_map = track_enabled or {}
    semitone_map = track_to_semitone_shift or {}
    velocity_map = track_to_velocity_scale or {}
    timing_map = track_to_timing_shift_ms or {}

    for track_idx, instrument in enumerate(midi.instruments):
        if not bool(enabled_map.get(track_idx, True)):
            instrument.notes = []
            continue

        if track_idx not in track_to_preset_name:
            continue

        preset_name = track_to_preset_name[track_idx]
        preset = INSTRUMENT_PRESETS[preset_name]

        instrument.program = preset.gm_program
        instrument.name = preset.name

        semitone_shift = int(semitone_map.get(track_idx, 0))
        velocity_scale = float(velocity_map.get(track_idx, 1.0))
        timing_shift_s = float(timing_map.get(track_idx, 0)) / 1000.0

        for note in instrument.notes:
            if semitone_shift != 0:
                note.pitch = max(0, min(127, int(note.pitch + semitone_shift)))

            if abs(velocity_scale - 1.0) > 1e-6:
                scaled = int(round(note.velocity * velocity_scale))
                note.velocity = max(1, min(127, scaled))

            if abs(timing_shift_s) > 1e-6:
                duration = max(0.01, note.end - note.start)
                note.start = max(0.0, note.start + timing_shift_s)
                note.end = max(note.start + 0.01, note.start + duration)

    midi.instruments = [inst for inst in midi.instruments if len(inst.notes) > 0]

    _set_global_sustain_pedal(midi, enabled=enable_sustain_pedal)

    midi.write(str(out_midi_path))

    score = converter.parse(str(out_midi_path))
    score.write("musicxml", fp=str(out_musicxml_path))

    _render_with_soundfont(
        midi=midi,
        soundfont_path=soundfont_path,
        preview_wav_path=out_preview_wav_path,
    )

    return out_midi_path, out_musicxml_path, out_preview_wav_path
