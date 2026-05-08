"""Audio analysis and transcription pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

import librosa
import numpy as np
import pretty_midi
import soundfile as sf
from basic_pitch.inference import predict
from music21 import converter


@dataclass
class LayerResult:
    name: str
    audio_path: Path
    energy_ratio: float
    midi_path: Path | None
    musicxml_path: Path | None
    note_count: int
    estimated_instrument: str
    confidence: float


@dataclass
class AnalysisResult:
    source_audio_path: Path
    full_midi_path: Path
    full_musicxml_path: Path
    full_note_count: int
    layers: list[LayerResult]


@dataclass(frozen=True)
class TranscriptionTuning:
    onset_threshold: float = 0.58
    frame_threshold: float = 0.24
    minimum_note_length_ms: float = 170.0
    min_output_note_length_ms: float = 110.0
    merge_gap_ms: float = 120.0
    legato_extension_ms: float = 65.0
    flicker_merge_gap_ms: float = 45.0
    sustain_boost: float = 0.08


@dataclass(frozen=True)
class StemCandidate:
    name: str
    audio_path: Path
    note_ratio: float
    min_frequency: float | None
    max_frequency: float | None
    default_program: int
    estimated_instrument: str
    confidence: float


def _normalize_audio(y: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(y))) if y.size > 0 else 0.0
    if peak <= 1e-8:
        return y
    return y / peak


def _extract_replica_stems(
    audio_path: Path,
    out_dir: Path,
    min_layer_note_ratio: float,
    sample_rate: int = 22050,
) -> list[StemCandidate]:
    y, sr = librosa.load(str(audio_path), sr=sample_rate, mono=True)
    if y.size == 0:
        return []

    y = _normalize_audio(y)
    harmonic, percussive = librosa.effects.hpss(y)

    n_fft = 4096
    hop = 512
    h_stft = librosa.stft(harmonic, n_fft=n_fft, hop_length=hop)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    stem_specs = [
        ("Bass Stem", 28.0, 220.0, 33, "Estimated Electric/Finger Bass", 0.82),
        ("Harmony Stem", 220.0, 2000.0, 0, "Estimated Piano/Guitar/Pad", 0.72),
        ("Lead Stem", 2000.0, 8000.0, 40, "Estimated Lead/Strings/Woodwind", 0.69),
    ]

    energies: list[tuple[str, Path, float, float, float, int, str, float]] = []
    total_energy = 0.0

    for stem_name, fmin, fmax, default_program, label, confidence in stem_specs:
        mask = ((freqs >= fmin) & (freqs < fmax)).astype(np.float32)
        stem_stft = h_stft * mask[:, np.newaxis]
        stem_audio = librosa.istft(stem_stft, hop_length=hop, length=len(y))
        stem_audio = _normalize_audio(stem_audio)
        energy = float(np.mean(np.square(stem_audio)))
        total_energy += max(energy, 0.0)

        stem_path = out_dir / f"{stem_name.lower().replace(' ', '_')}.wav"
        sf.write(str(stem_path), stem_audio, sr)
        energies.append((stem_name, stem_path, energy, fmin, fmax, default_program, label, confidence))

    # Percussive stem can still carry pitched transients useful for replica detail.
    percussive = _normalize_audio(percussive)
    perc_energy = float(np.mean(np.square(percussive)))
    total_energy += max(perc_energy, 0.0)
    perc_path = out_dir / "percussive_stem.wav"
    sf.write(str(perc_path), percussive, sr)
    energies.append(("Percussive Stem", perc_path, perc_energy, 45.0, 2400.0, 115, "Estimated Percussive Layer", 0.62))

    if total_energy <= 1e-9:
        return []

    stems: list[StemCandidate] = []
    for stem_name, stem_path, energy, fmin, fmax, program, label, confidence in energies:
        ratio = energy / total_energy
        if ratio < min_layer_note_ratio:
            continue
        stems.append(
            StemCandidate(
                name=stem_name,
                audio_path=stem_path,
                note_ratio=ratio,
                min_frequency=fmin,
                max_frequency=fmax,
                default_program=program,
                estimated_instrument=label,
                confidence=confidence,
            )
        )

    stems.sort(key=lambda s: s.min_frequency or 0.0)
    return stems


def _copy_note(note: pretty_midi.Note) -> pretty_midi.Note:
    return pretty_midi.Note(
        velocity=int(note.velocity),
        pitch=int(note.pitch),
        start=float(note.start),
        end=float(note.end),
    )


def _merge_same_pitch_notes(
    notes: list[pretty_midi.Note],
    min_duration_s: float,
    merge_gap_s: float,
    max_overlap_s: float = 0.045,
) -> list[pretty_midi.Note]:
    if not notes:
        return []

    sorted_notes = sorted(notes, key=lambda n: (n.start, n.end))
    merged: list[pretty_midi.Note] = []

    for note in sorted_notes:
        if (note.end - note.start) < min_duration_s * 0.4:
            continue

        current = _copy_note(note)
        if not merged:
            merged.append(current)
            continue

        prev = merged[-1]
        near_duplicate_start = abs(current.start - prev.start) <= 0.02
        gap = current.start - prev.end

        if near_duplicate_start:
            prev.end = max(prev.end, current.end)
            prev.velocity = max(prev.velocity, current.velocity)
            continue

        if -max_overlap_s <= gap <= merge_gap_s:
            prev.end = max(prev.end, current.end)
            prev.velocity = int((prev.velocity + current.velocity) / 2)
            continue

        merged.append(current)

    return merged


def _stabilize_pitch_flicker(notes: list[pretty_midi.Note], flicker_gap_s: float) -> list[pretty_midi.Note]:
    if len(notes) <= 1:
        return notes

    notes = sorted(notes, key=lambda n: (n.start, n.pitch))
    stabilized: list[pretty_midi.Note] = []

    for current in notes:
        note = _copy_note(current)
        if not stabilized:
            stabilized.append(note)
            continue

        prev = stabilized[-1]
        gap = note.start - prev.end
        prev_len = max(0.0, prev.end - prev.start)
        note_len = max(0.0, note.end - note.start)

        # Collapse tiny adjacent pitch flickers (e.g., 59<->60) into one sustained note.
        if gap <= flicker_gap_s and abs(int(note.pitch) - int(prev.pitch)) <= 1 and max(prev_len, note_len) <= 0.28:
            keep_pitch = prev.pitch if prev_len >= note_len else note.pitch
            prev.pitch = int(keep_pitch)
            prev.end = max(prev.end, note.end)
            prev.velocity = int((prev.velocity + note.velocity) / 2)
            continue

        stabilized.append(note)

    return stabilized


def _apply_legato_extension(notes: list[pretty_midi.Note], extension_s: float) -> None:
    if extension_s <= 1e-6 or len(notes) <= 1:
        return

    notes.sort(key=lambda n: (n.start, n.pitch))
    for idx in range(len(notes) - 1):
        note = notes[idx]
        next_note = notes[idx + 1]
        next_start = float(next_note.start)
        target_end = min(next_start - 0.01, note.end + extension_s)
        if target_end > note.end:
            note.end = max(note.start + 0.01, target_end)


def _post_process_midi_notes(midi: pretty_midi.PrettyMIDI, tuning: TranscriptionTuning) -> pretty_midi.PrettyMIDI:
    min_duration_s = max(0.02, tuning.min_output_note_length_ms / 1000.0)
    merge_gap_s = max(0.01, tuning.merge_gap_ms / 1000.0)
    legato_s = max(0.0, tuning.legato_extension_ms / 1000.0)
    flicker_gap_s = max(0.005, tuning.flicker_merge_gap_ms / 1000.0)

    for instrument in midi.instruments:
        if instrument.is_drum:
            continue

        by_pitch: dict[int, list[pretty_midi.Note]] = {}
        for note in instrument.notes:
            by_pitch.setdefault(int(note.pitch), []).append(note)

        rebuilt: list[pretty_midi.Note] = []
        for pitch_notes in by_pitch.values():
            rebuilt.extend(_merge_same_pitch_notes(pitch_notes, min_duration_s=min_duration_s, merge_gap_s=merge_gap_s))

        _apply_legato_extension(rebuilt, extension_s=legato_s)

        rebuilt = _stabilize_pitch_flicker(rebuilt, flicker_gap_s=flicker_gap_s)
        filtered = [n for n in rebuilt if (n.end - n.start) >= min_duration_s]
        filtered.sort(key=lambda n: (n.start, n.pitch))
        instrument.notes = filtered

    return midi


def _run_predict_pass(
    audio_path: Path,
    onset_threshold: float,
    frame_threshold: float,
    minimum_note_length_ms: float,
    minimum_frequency: float | None = None,
    maximum_frequency: float | None = None,
) -> pretty_midi.PrettyMIDI:
    _model_output, midi_data, _note_events = predict(
        str(audio_path),
        onset_threshold=float(onset_threshold),
        frame_threshold=float(frame_threshold),
        minimum_note_length=float(minimum_note_length_ms),
        minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency,
        melodia_trick=True,
    )
    return midi_data


def _notes_by_pitch(midi: pretty_midi.PrettyMIDI) -> dict[int, list[pretty_midi.Note]]:
    grouped: dict[int, list[pretty_midi.Note]] = {}
    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            grouped.setdefault(int(note.pitch), []).append(note)

    for pitch in grouped:
        grouped[pitch].sort(key=lambda n: (n.start, n.end))
    return grouped


def _fuse_primary_and_sustain(primary: pretty_midi.PrettyMIDI, sustain: pretty_midi.PrettyMIDI) -> pretty_midi.PrettyMIDI:
    fused = pretty_midi.PrettyMIDI()
    primary_grouped = _notes_by_pitch(primary)
    sustain_grouped = _notes_by_pitch(sustain)

    all_pitches = sorted(set(primary_grouped.keys()) | set(sustain_grouped.keys()))
    inst = pretty_midi.Instrument(program=0, name="Fused Transcription", is_drum=False)

    for pitch in all_pitches:
        p_notes = [_copy_note(n) for n in primary_grouped.get(pitch, [])]
        s_notes = sustain_grouped.get(pitch, [])

        for p_note in p_notes:
            overlap_candidates = [
                s_note
                for s_note in s_notes
                if (s_note.start <= p_note.end + 0.18 and s_note.end >= p_note.start - 0.06)
            ]
            if not overlap_candidates:
                continue

            best = max(overlap_candidates, key=lambda n: n.end - n.start)
            p_note.end = max(p_note.end, best.end)
            p_note.start = min(p_note.start, best.start + 0.02)

        # Add sustain-only notes if primary entirely missed them.
        for s_note in s_notes:
            if (s_note.end - s_note.start) < 0.2:
                continue
            has_neighbor = any(
                abs(s_note.start - p_note.start) <= 0.15 or (s_note.start <= p_note.end and s_note.end >= p_note.start)
                for p_note in p_notes
            )
            if not has_neighbor:
                p_notes.append(_copy_note(s_note))

        inst.notes.extend(sorted(p_notes, key=lambda n: (n.start, n.end)))

    fused.instruments.append(inst)
    return fused


def _copy_notes(notes: list[pretty_midi.Note]) -> list[pretty_midi.Note]:
    return [
        pretty_midi.Note(
            velocity=int(n.velocity),
            pitch=int(n.pitch),
            start=float(n.start),
            end=float(n.end),
        )
        for n in notes
    ]


def _simple_kmeans(features: np.ndarray, n_clusters: int, max_iter: int = 24) -> np.ndarray:
    if n_clusters <= 1 or len(features) <= 1:
        return np.zeros(len(features), dtype=np.int32)

    pitch_sorted = np.argsort(features[:, 0])
    seed_ids = np.linspace(0, len(pitch_sorted) - 1, n_clusters, dtype=int)
    centroids = features[pitch_sorted[seed_ids]].copy()

    labels = np.zeros(len(features), dtype=np.int32)
    for _ in range(max_iter):
        distances = np.sum((features[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
        new_labels = np.argmin(distances, axis=1).astype(np.int32)

        if np.array_equal(new_labels, labels):
            break
        labels = new_labels

        for cluster_idx in range(n_clusters):
            points = features[labels == cluster_idx]
            if len(points) > 0:
                centroids[cluster_idx] = points.mean(axis=0)

    return labels


def _choose_layer_count(note_count: int) -> int:
    if note_count < 40:
        return 1
    if note_count < 180:
        return 2
    if note_count < 450:
        return 3
    return 4


def _estimate_layer_profile(mean_pitch: float, mean_duration: float, density: float) -> tuple[str, int, float]:
    if mean_pitch <= 47:
        confidence = min(0.9, 0.64 + (47 - mean_pitch) / 55)
        return "Estimated Bass Instrument", 33, float(confidence)

    if density >= 5.8 and mean_duration < 0.24:
        confidence = min(0.85, 0.58 + (density - 5.8) / 10)
        return "Estimated Plucked/Perc Layer", 24, float(confidence)

    if mean_pitch >= 74 and mean_duration >= 0.34:
        confidence = min(0.9, 0.6 + (mean_pitch - 74) / 55)
        return "Estimated Lead Melody", 40, float(confidence)

    if mean_duration >= 0.85:
        confidence = min(0.86, 0.62 + (mean_duration - 0.85) / 2)
        return "Estimated Strings/Pad", 48, float(confidence)

    return "Estimated Harmony Instrument", 0, 0.58


def _write_musicxml_from_midi(midi_path: Path, xml_path: Path) -> None:
    score = converter.parse(str(midi_path))
    score.write("musicxml", fp=str(xml_path))


def _collect_note_bundle(midi: pretty_midi.PrettyMIDI) -> list[tuple[pretty_midi.Note, int]]:
    bundle: list[tuple[pretty_midi.Note, int]] = []
    for track_idx, instrument in enumerate(midi.instruments):
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            bundle.append((note, track_idx))
    return bundle


def _build_instrument_layers_from_midi(
    source_midi_path: Path,
    out_dir: Path,
    min_layer_note_ratio: float,
    target_layer_count: int | None,
) -> tuple[Path, Path, list[LayerResult], int]:
    source_midi = pretty_midi.PrettyMIDI(str(source_midi_path))
    note_bundle = _collect_note_bundle(source_midi)

    if not note_bundle:
        layered_midi_path = out_dir / "full_mix_layered.mid"
        layered_xml_path = out_dir / "full_mix_layered.musicxml"
        shutil.copyfile(source_midi_path, layered_midi_path)
        _write_musicxml_from_midi(layered_midi_path, layered_xml_path)
        return layered_midi_path, layered_xml_path, [], 0

    duration = max(1.0, float(source_midi.get_end_time()))
    notes = [n for n, _track in note_bundle]
    features = np.array(
        [
            [n.pitch / 127.0, n.start / duration, min((n.end - n.start) / 2.5, 1.0), n.velocity / 127.0]
            for n in notes
        ],
        dtype=np.float32,
    )

    if target_layer_count is None:
        n_clusters = min(_choose_layer_count(len(notes)), len(notes))
    else:
        n_clusters = max(1, min(int(target_layer_count), len(notes)))
    labels = _simple_kmeans(features, n_clusters=n_clusters)

    cluster_payload: list[dict[str, object]] = []
    total_notes = len(notes)

    for cluster_idx in range(n_clusters):
        idxs = np.where(labels == cluster_idx)[0]
        if len(idxs) == 0:
            continue

        cluster_notes = [notes[i] for i in idxs]
        ratio = len(cluster_notes) / total_notes
        if ratio < min_layer_note_ratio and n_clusters > 1:
            continue

        pitches = np.array([n.pitch for n in cluster_notes], dtype=np.float32)
        durations = np.array([n.end - n.start for n in cluster_notes], dtype=np.float32)
        density = len(cluster_notes) / duration

        label_name, gm_program, confidence = _estimate_layer_profile(
            mean_pitch=float(np.mean(pitches)),
            mean_duration=float(np.mean(durations)),
            density=float(density),
        )

        cluster_payload.append(
            {
                "name": label_name,
                "program": gm_program,
                "confidence": confidence,
                "ratio": ratio,
                "notes": cluster_notes,
                "mean_pitch": float(np.mean(pitches)),
            }
        )

    if not cluster_payload:
        cluster_payload.append(
            {
                "name": "Estimated Full Instrument Layer",
                "program": 0,
                "confidence": 0.45,
                "ratio": 1.0,
                "notes": notes,
                "mean_pitch": float(np.mean([n.pitch for n in notes])),
            }
        )

    cluster_payload.sort(key=lambda payload: float(payload["mean_pitch"]))

    layered_midi = pretty_midi.PrettyMIDI()
    layered_results: list[LayerResult] = []

    for layer_idx, payload in enumerate(cluster_payload, start=1):
        layer_notes = _copy_notes(payload["notes"])
        layer_name = f"Layer {layer_idx}: {payload['name']}"
        program = int(payload["program"])

        inst = pretty_midi.Instrument(program=program, name=layer_name, is_drum=False)
        inst.notes = layer_notes
        layered_midi.instruments.append(inst)

        layer_midi = pretty_midi.PrettyMIDI()
        layer_inst = pretty_midi.Instrument(program=program, name=layer_name, is_drum=False)
        layer_inst.notes = _copy_notes(layer_notes)
        layer_midi.instruments.append(layer_inst)

        layer_stem = f"layer_{layer_idx:02d}"
        layer_midi_path = out_dir / f"{layer_stem}.mid"
        layer_xml_path = out_dir / f"{layer_stem}.musicxml"
        layer_audio_path = out_dir / f"{layer_stem}.wav"

        layer_midi.write(str(layer_midi_path))
        _write_musicxml_from_midi(layer_midi_path, layer_xml_path)

        layer_audio = layer_midi.synthesize(fs=22050)
        peak = float(np.max(np.abs(layer_audio)))
        if peak > 1e-6:
            layer_audio = 0.95 * (layer_audio / peak)
        sf.write(str(layer_audio_path), layer_audio.astype(np.float32), 22050)

        layered_results.append(
            LayerResult(
                name=layer_name,
                audio_path=layer_audio_path,
                energy_ratio=float(payload["ratio"]),
                midi_path=layer_midi_path,
                musicxml_path=layer_xml_path,
                note_count=len(layer_notes),
                estimated_instrument=str(payload["name"]),
                confidence=float(payload["confidence"]),
            )
        )

    layered_midi_path = out_dir / "full_mix_layered.mid"
    layered_xml_path = out_dir / "full_mix_layered.musicxml"
    layered_midi.write(str(layered_midi_path))
    _write_musicxml_from_midi(layered_midi_path, layered_xml_path)

    full_note_count = sum(len(inst.notes) for inst in layered_midi.instruments)
    return layered_midi_path, layered_xml_path, layered_results, full_note_count


def _build_layers_from_replica_stems(
    audio_path: Path,
    out_dir: Path,
    min_layer_note_ratio: float,
    tuning: TranscriptionTuning,
) -> tuple[Path, Path, list[LayerResult], int]:
    stem_candidates = _extract_replica_stems(
        audio_path=audio_path,
        out_dir=out_dir,
        min_layer_note_ratio=min_layer_note_ratio,
    )

    if not stem_candidates:
        raise RuntimeError("No valid stems extracted for replica transcription.")

    full_midi = pretty_midi.PrettyMIDI()
    layers: list[LayerResult] = []

    for idx, stem in enumerate(stem_candidates, start=1):
        layer_stem = f"replica_layer_{idx:02d}_{stem.name.lower().replace(' ', '_')}"
        layer_midi_path, layer_xml_path, note_count = _transcribe_to_midi_and_xml(
            audio_path=stem.audio_path,
            out_stem=layer_stem,
            out_dir=out_dir,
            tuning=tuning,
            minimum_frequency=stem.min_frequency,
            maximum_frequency=stem.max_frequency,
        )

        layer_pm = pretty_midi.PrettyMIDI(str(layer_midi_path))
        layer_notes: list[pretty_midi.Note] = []
        for inst in layer_pm.instruments:
            layer_notes.extend(_copy_notes(inst.notes))

        if len(layer_notes) == 0:
            continue

        layer_notes.sort(key=lambda n: (n.start, n.pitch))
        layer_name = f"Layer {len(layers) + 1}: {stem.estimated_instrument}"

        merged_inst = pretty_midi.Instrument(program=stem.default_program, name=layer_name, is_drum=False)
        merged_inst.notes = layer_notes
        full_midi.instruments.append(merged_inst)

        layers.append(
            LayerResult(
                name=layer_name,
                audio_path=stem.audio_path,
                energy_ratio=stem.note_ratio,
                midi_path=layer_midi_path,
                musicxml_path=layer_xml_path,
                note_count=note_count,
                estimated_instrument=stem.estimated_instrument,
                confidence=stem.confidence,
            )
        )

    if len(full_midi.instruments) == 0:
        raise RuntimeError("Stem transcription produced no notes.")

    full_midi_path = out_dir / "full_mix_layered.mid"
    full_xml_path = out_dir / "full_mix_layered.musicxml"
    full_midi.write(str(full_midi_path))
    _write_musicxml_from_midi(full_midi_path, full_xml_path)

    full_note_count = sum(len(inst.notes) for inst in full_midi.instruments)
    return full_midi_path, full_xml_path, layers, full_note_count


def _transcribe_to_midi_and_xml(
    audio_path: Path,
    out_stem: str,
    out_dir: Path,
    tuning: TranscriptionTuning,
    minimum_frequency: float | None = None,
    maximum_frequency: float | None = None,
) -> tuple[Path, Path, int]:
    primary_midi = _run_predict_pass(
        audio_path=audio_path,
        onset_threshold=float(tuning.onset_threshold),
        frame_threshold=float(tuning.frame_threshold),
        minimum_note_length_ms=float(tuning.minimum_note_length_ms),
        minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency,
    )

    sustain_midi = _run_predict_pass(
        audio_path=audio_path,
        onset_threshold=min(0.95, float(tuning.onset_threshold + tuning.sustain_boost)),
        frame_threshold=max(0.08, float(tuning.frame_threshold - tuning.sustain_boost)),
        minimum_note_length_ms=float(tuning.minimum_note_length_ms * 1.25),
        minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency,
    )

    midi_data = _fuse_primary_and_sustain(primary=primary_midi, sustain=sustain_midi)
    midi_data = _post_process_midi_notes(midi_data, tuning=tuning)

    midi_path = out_dir / f"{out_stem}.mid"
    midi_data.write(str(midi_path))

    note_count = sum(len(track.notes) for track in midi_data.instruments)

    musicxml_path = out_dir / f"{out_stem}.musicxml"
    _write_musicxml_from_midi(midi_path, musicxml_path)

    return midi_path, musicxml_path, note_count


def analyze_audio(
    audio_path: Path,
    output_root: Path,
    detect_layers: bool = True,
    transcribe_detected_layers: bool = True,
    replica_mode: bool = True,
    min_layer_energy_ratio: float = 0.08,
    target_layer_count: int | None = None,
    onset_threshold: float = 0.58,
    frame_threshold: float = 0.24,
    minimum_note_length_ms: float = 170.0,
    min_output_note_length_ms: float = 110.0,
    merge_gap_ms: float = 120.0,
    legato_extension_ms: float = 65.0,
    flicker_merge_gap_ms: float = 45.0,
    sustain_boost: float = 0.08,
) -> AnalysisResult:
    output_root.mkdir(parents=True, exist_ok=True)

    tuning = TranscriptionTuning(
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length_ms=minimum_note_length_ms,
        min_output_note_length_ms=min_output_note_length_ms,
        merge_gap_ms=merge_gap_ms,
        legato_extension_ms=legato_extension_ms,
        flicker_merge_gap_ms=flicker_merge_gap_ms,
        sustain_boost=sustain_boost,
    )

    if detect_layers and replica_mode:
        try:
            full_midi_path, full_musicxml_path, detected_layers, full_note_count = _build_layers_from_replica_stems(
                audio_path=audio_path,
                out_dir=output_root,
                min_layer_note_ratio=min_layer_energy_ratio,
                tuning=tuning,
            )
            layers = detected_layers if transcribe_detected_layers else []
            return AnalysisResult(
                source_audio_path=audio_path,
                full_midi_path=full_midi_path,
                full_musicxml_path=full_musicxml_path,
                full_note_count=full_note_count,
                layers=layers,
            )
        except Exception:
            # Fallback to clustering path when stem-guided replica mode fails.
            pass

    raw_midi_path, raw_musicxml_path, raw_note_count = _transcribe_to_midi_and_xml(
        audio_path=audio_path,
        out_stem="full_mix_raw",
        out_dir=output_root,
        tuning=tuning,
    )

    if detect_layers:
        full_midi_path, full_musicxml_path, detected_layers, full_note_count = _build_instrument_layers_from_midi(
            source_midi_path=raw_midi_path,
            out_dir=output_root,
            min_layer_note_ratio=min_layer_energy_ratio,
            target_layer_count=target_layer_count,
        )
        layers = detected_layers if transcribe_detected_layers else []
    else:
        full_midi_path = raw_midi_path
        full_musicxml_path = raw_musicxml_path
        full_note_count = raw_note_count
        layers = []

    return AnalysisResult(
        source_audio_path=audio_path,
        full_midi_path=full_midi_path,
        full_musicxml_path=full_musicxml_path,
        full_note_count=full_note_count,
        layers=layers,
    )


def midi_notes_table(midi_path: Path, max_rows: int = 400) -> list[dict[str, float | str | int]]:
    midi = pretty_midi.PrettyMIDI(str(midi_path))

    tempo_changes, tempi = midi.get_tempo_changes()
    tempo_bpm = float(tempi[0]) if len(tempi) > 0 else 120.0

    rows: list[dict[str, float | str | int]] = []
    for track_idx, instrument in enumerate(midi.instruments):
        for note in instrument.notes:
            rows.append(
                {
                    "track": track_idx,
                    "instrument": instrument.name or pretty_midi.program_to_instrument_name(instrument.program),
                    "pitch": pretty_midi.note_number_to_name(note.pitch),
                    "start_beat": round(note.start * tempo_bpm / 60.0, 3),
                    "duration_beat": round((note.end - note.start) * tempo_bpm / 60.0, 3),
                    "velocity": note.velocity,
                }
            )

    rows.sort(key=lambda r: (r["start_beat"], r["track"]))
    return rows[:max_rows]
