from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from music_identifier import (  # noqa: E402
    DEFAULT_SOUNDFONT_NAME,
    INSTRUMENT_PRESETS,
    PRESET_NAMES,
    analyze_audio,
    apply_instrument_map_and_render_preview,
    ensure_default_soundfont,
    list_midi_tracks,
)
from music_identifier.pipeline import midi_notes_table  # noqa: E402

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Music Sheet Builder", page_icon="M", layout="wide")


# Distinct visual direction: editorial typography + layered cards.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=Plus+Jakarta+Sans:wght@400;500;700&display=swap');

    :root {
        --ink: #13242d;
        --ink-soft: #314a57;
        --panel: rgba(255, 255, 255, 0.87);
        --line: rgba(19, 36, 45, 0.14);
        --hot: #ef6236;
        --sun: #f2bc4a;
        --teal: #10958a;
        --ocean: #25556f;
    }

    .stApp {
        background:
            radial-gradient(72% 95% at 0% -10%, rgba(239,98,54,0.24), transparent 60%),
            radial-gradient(60% 76% at 103% 8%, rgba(37,85,111,0.24), transparent 58%),
            radial-gradient(38% 44% at 78% 98%, rgba(242,188,74,0.24), transparent 62%),
            linear-gradient(138deg, #f7efe4 0%, #e7f3ee 52%, #e7f0f7 100%);
    }

    .block-container {
        max-width: 1360px;
        padding-top: 0.9rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        font-family: 'Syne', sans-serif;
        color: var(--ink);
        letter-spacing: 0.2px;
    }

    p, span, label, li, div {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: var(--ink-soft);
    }

    .hero-shell {
        border-radius: 24px;
        border: 1px solid var(--line);
        background: linear-gradient(132deg, rgba(255,255,255,0.94), rgba(255,255,255,0.78));
        box-shadow: 0 18px 52px rgba(8, 38, 56, 0.12);
        overflow: hidden;
        margin-bottom: 1.05rem;
    }

    .hero-banner {
        background: linear-gradient(105deg, var(--hot), var(--sun));
        color: #fff;
        padding: 0.72rem 1rem;
        font-weight: 800;
        letter-spacing: 0.34px;
        font-size: 0.84rem;
        text-transform: uppercase;
    }

    .hero-content {
        padding: 1.15rem 1.3rem 1.25rem 1.3rem;
    }

    .chip-row {
        margin-top: 0.75rem;
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
    }

    .chip {
        border-radius: 999px;
        border: 1px solid rgba(16,149,138,0.30);
        background: rgba(16,149,138,0.12);
        color: #0b655d;
        padding: 0.26rem 0.68rem;
        font-size: 0.73rem;
        font-weight: 700;
    }

    .section-card {
        border: 1px solid var(--line);
        border-radius: 20px;
        background: var(--panel);
        box-shadow: 0 12px 32px rgba(9, 34, 48, 0.10);
        padding: 0.78rem 1rem 0.95rem 1rem;
        margin-top: 0.62rem;
        backdrop-filter: blur(4px);
        position: relative;
    }

    .section-card::before {
        content: "";
        position: absolute;
        left: 0;
        right: 0;
        top: 0;
        height: 4px;
        border-radius: 20px 20px 0 0;
        background: linear-gradient(90deg, rgba(16,149,138,0.42), rgba(37,85,111,0.12));
    }

    .section-title {
        font-family: 'Syne', sans-serif;
        font-size: 1.02rem;
        font-weight: 800;
        color: var(--ocean);
        letter-spacing: 0.2px;
        margin: 0.1rem 0 0.55rem 0;
    }

    .divider-line {
        width: 100%;
        height: 1px;
        background: linear-gradient(90deg, rgba(31,79,107,0.24), rgba(31,79,107,0.02));
        margin: 0.45rem 0 0.8rem 0;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1f4359 0%, #275d79 58%, #2a6e8f 100%);
    }

    [data-testid="stSidebar"] * {
        color: #ecf4ff !important;
    }

    .stButton > button {
        min-height: 2.75rem;
        border: none;
        border-radius: 13px;
        background: linear-gradient(118deg, var(--hot), var(--sun));
        color: #fff;
        font-weight: 800;
        letter-spacing: 0.3px;
        box-shadow: 0 7px 20px rgba(240,95,46,0.30);
    }

    .stButton > button:hover {
        filter: brightness(1.03);
        transform: translateY(-1px);
        transition: all .15s ease;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.45rem;
        background: rgba(255,255,255,0.55);
        border: 1px solid rgba(19,36,45,0.1);
        border-radius: 12px;
        padding: 0.25rem;
    }

    .stTabs [data-baseweb="tab"] {
        height: 2.25rem;
        border-radius: 9px;
        padding: 0 0.8rem;
        font-family: 'Syne', sans-serif;
        font-weight: 700;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(110deg, rgba(16,149,138,0.20), rgba(37,85,111,0.20)) !important;
    }

    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.78);
        border: 1px solid rgba(31,79,107,0.16);
        border-radius: 14px;
        padding: 0.5rem 0.65rem;
    }

    @media (max-width: 920px) {
        .block-container {
            padding-top: 0.6rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }

        .hero-content {
            padding: 1rem 0.95rem 1rem 0.95rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _timestamp_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _audio_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".mp3":
        return "audio/mpeg"
    if ext == ".m4a":
        return "audio/mp4"
    if ext == ".flac":
        return "audio/flac"
    return "audio/wav"


def _source_signature(name: str, data: bytes) -> str:
    digest = hashlib.sha1(data).hexdigest()[:12]
    return f"{name.lower()}::{len(data)}::{digest}"


def _sanitize_musicxml(xml_text: str) -> str:
    """Patch common MusicXML omissions that can crash browser renderers."""
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return xml_text

    for time_node in root.findall(".//time"):
        beats = time_node.find("beats")
        beat_type = time_node.find("beat-type")
        if beats is None:
            beats = ET.SubElement(time_node, "beats")
            beats.text = "4"
        if beat_type is None:
            beat_type = ET.SubElement(time_node, "beat-type")
            beat_type.text = "4"
        if not (beats.text or "").strip():
            beats.text = "4"
        if not (beat_type.text or "").strip():
            beat_type.text = "4"

    return ET.tostring(root, encoding="unicode")


def _render_musicxml_sheet(xml_path: Path, widget_id: str, height: int = 760) -> None:
    xml_text_raw = xml_path.read_text(encoding="utf-8", errors="ignore")
    xml_text = _sanitize_musicxml(xml_text_raw)

    try:
        import verovio  # Local import to avoid hard failure if dependency is missing.

        tk = verovio.toolkit()
        tk.setOptions(
            {
                "scale": 36,
                "pageWidth": 2100,
                "pageHeight": 3300,
                "header": "none",
                "footer": "none",
                "adjustPageHeight": True,
                "breaks": "auto",
                "svgViewBox": True,
            }
        )

        # First attempt: let verovio parse directly from file to preserve headers/encoding.
        load_ok = bool(tk.loadFile(str(xml_path)))
        page_count = int(tk.getPageCount() or 0)

        # Second attempt: sanitized in-memory XML for malformed timing metadata.
        if (not load_ok) or page_count < 1:
            tk.resetOptions()
            tk.setOptions(
                {
                    "scale": 36,
                    "pageWidth": 2100,
                    "pageHeight": 3300,
                    "header": "none",
                    "footer": "none",
                    "adjustPageHeight": True,
                    "breaks": "auto",
                    "svgViewBox": True,
                }
            )
            load_ok = bool(tk.loadData(xml_text))
            page_count = int(tk.getPageCount() or 0)

        if (not load_ok) or page_count < 1:
            raise RuntimeError("Verovio could not parse this MusicXML (page count is zero).")

        page = st.slider(
            "Score Page",
            min_value=1,
            max_value=page_count,
            value=1,
            key=f"sheet_page::{widget_id}",
        )

        svg = tk.renderToSVG(page)
        st.markdown(
            f"""
            <div style=\"max-height:{height}px; overflow:auto; background:linear-gradient(180deg, rgba(255,255,255,0.99), rgba(247,251,252,0.99)); border:1px solid rgba(15,32,40,0.16); border-radius:14px; padding:10px; box-shadow: inset 0 0 0 1px rgba(16,149,138,0.08);\">{svg}</div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Page {page} / {page_count}")
        return
    except Exception as exc:
        st.warning("Sheet render failed. Download the MusicXML file as fallback.")
        with st.expander("Sheet Viewer Diagnostics"):
            st.code(str(exc))


def _clear_track_widget_state(active_analysis_id: str | None = None) -> None:
    for key in list(st.session_state.keys()):
        if not key.startswith("trackcfg::"):
            continue
        if active_analysis_id is not None and key.startswith(f"trackcfg::{active_analysis_id}::"):
            continue
        st.session_state.pop(key, None)


def _reset_analysis_state() -> None:
    for key in ["analysis", "run_dir", "analysis_id", "arrangement", "input_signature"]:
        st.session_state.pop(key, None)
    _clear_track_widget_state(active_analysis_id=None)


st.markdown(
    """
    <div class="hero-shell">
        <div class="hero-banner">Studio Transcription Engine</div>
        <div class="hero-content">
            <h1 style="margin-bottom:0.3rem;">Music Sheet Builder</h1>
            <p style="margin:0;">Transcribe recordings into readable notation, audition arrangement ideas, and view score pages directly in the app using your selected render instruments.</p>
            <div class="chip-row">
                <span class="chip">Audio to Score</span>
                <span class="chip">Multi-pass Identification</span>
                <span class="chip">In-app Sheet Viewer</span>
                <span class="chip">Creative Transform</span>
                <span class="chip">SoundFont + Pedal</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Project Controls")
    if st.button("Reset Current Analysis", use_container_width=True):
        _reset_analysis_state()
        st.rerun()

    st.header("Identification")
    replica_mode = st.checkbox(
        "Replica mode (stem-guided)",
        value=True,
        help="Runs stem-separated multi-pass transcription for closer instrument/layer replicas.",
    )
    detect_layers = st.checkbox("Estimate instrument layers", value=True)
    export_layers = st.checkbox("Export each detected layer", value=True)
    target_layer_count = st.slider(
        "Target layer count",
        min_value=1,
        max_value=8,
        value=4,
        step=1,
        help="Increase for dense arrangements where instruments merge together.",
    )
    min_layer_note_ratio = st.slider(
        "Minimum layer note share",
        min_value=0.02,
        max_value=0.25,
        value=0.06,
        step=0.01,
    )

    with st.expander("Advanced Identification", expanded=True):
        onset_threshold = st.slider("Onset sensitivity", 0.35, 0.85, 0.58, 0.01)
        frame_threshold = st.slider("Frame sensitivity", 0.08, 0.50, 0.23, 0.01)
        minimum_note_length_ms = st.slider("Model minimum note (ms)", 60, 520, 180, 5)
        min_output_note_length_ms = st.slider("Final minimum note (ms)", 40, 380, 115, 5)
        merge_gap_ms = st.slider("Merge split-note gap (ms)", 20, 350, 130, 5)
        legato_extension_ms = st.slider("Legato extension (ms)", 0, 260, 70, 5)
        flicker_merge_gap_ms = st.slider("Pitch flicker merge gap (ms)", 10, 120, 45, 5)
        sustain_boost = st.slider("Sustain fusion strength", 0.02, 0.20, 0.08, 0.01)

    st.header("Render")
    enable_sustain_pedal = st.checkbox("Enable sustain pedal (CC64)", value=False)
    auto_soundfont = st.checkbox("Use free MuseScore SoundFont", value=True)
    custom_soundfont = st.file_uploader("Custom SoundFont (.sf2/.sf3)", type=["sf2", "sf3"])

input_tab, record_tab = st.tabs(["Upload Audio", "Record Audio"])
uploaded_file = None
recorded_audio = None

with input_tab:
    uploaded_file = st.file_uploader("Upload MP3/WAV/M4A/FLAC", type=["mp3", "wav", "m4a", "flac"])
    if uploaded_file is not None:
        st.audio(uploaded_file.getvalue())

with record_tab:
    recorded_audio = st.audio_input("Record with microphone")
    if recorded_audio is not None:
        st.audio(recorded_audio.getvalue())

source_name = ""
source_bytes: bytes | None = None
if recorded_audio is not None:
    source_name = "recorded_input.wav"
    source_bytes = recorded_audio.getvalue()
elif uploaded_file is not None:
    source_name = uploaded_file.name
    source_bytes = uploaded_file.getvalue()

if st.button("Generate Sheet Music", type="primary", use_container_width=True):
    if source_bytes is None:
        st.error("Upload or record audio first.")
    else:
        run_id = _timestamp_id()
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        extension = Path(source_name).suffix.lower() or ".wav"
        source_path = run_dir / f"source{extension}"
        source_path.write_bytes(source_bytes)

        with st.spinner("Running multi-pass transcription and layer estimation..."):
            try:
                analysis = analyze_audio(
                    audio_path=source_path,
                    output_root=run_dir,
                    detect_layers=detect_layers,
                    transcribe_detected_layers=export_layers,
                    replica_mode=replica_mode,
                    min_layer_energy_ratio=min_layer_note_ratio,
                    target_layer_count=target_layer_count if detect_layers else None,
                    onset_threshold=float(onset_threshold),
                    frame_threshold=float(frame_threshold),
                    minimum_note_length_ms=float(minimum_note_length_ms),
                    min_output_note_length_ms=float(min_output_note_length_ms),
                    merge_gap_ms=float(merge_gap_ms),
                    legato_extension_ms=float(legato_extension_ms),
                    flicker_merge_gap_ms=float(flicker_merge_gap_ms),
                    sustain_boost=float(sustain_boost),
                )

                st.session_state["analysis"] = analysis
                st.session_state["run_dir"] = run_dir
                st.session_state["analysis_id"] = run_id
                st.session_state["input_signature"] = _source_signature(source_name, source_bytes)
                st.session_state.pop("arrangement", None)
                _clear_track_widget_state(active_analysis_id=run_id)
            except Exception as exc:
                st.exception(exc)

analysis = st.session_state.get("analysis")
run_dir: Path | None = st.session_state.get("run_dir")
analysis_id = str(st.session_state.get("analysis_id", "none"))

if analysis is not None:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Detected Notes", analysis.full_note_count)
    m2.metric("Detected Layers", len(analysis.layers))
    m3.metric("Source", analysis.source_audio_path.name)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Score Data</div><div class="divider-line"></div>', unsafe_allow_html=True)
    notes_df = pd.DataFrame(midi_notes_table(analysis.full_midi_path))
    if not notes_df.empty:
        st.dataframe(notes_df, use_container_width=True, height=310)
    else:
        st.info("No note rows available for preview.")

    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "Download Full MIDI",
        data=_read_bytes(analysis.full_midi_path),
        file_name=analysis.full_midi_path.name,
        mime="audio/midi",
    )
    d2.download_button(
        "Download Full MusicXML",
        data=_read_bytes(analysis.full_musicxml_path),
        file_name=analysis.full_musicxml_path.name,
        mime="application/vnd.recordare.musicxml+xml",
    )
    d3.download_button(
        "Download Source Audio",
        data=_read_bytes(analysis.source_audio_path),
        file_name=analysis.source_audio_path.name,
        mime=_audio_mime(analysis.source_audio_path),
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if analysis.layers:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Instrument Layers</div><div class="divider-line"></div>', unsafe_allow_html=True)
        for layer_idx, layer in enumerate(analysis.layers):
            with st.expander(f"{layer.name} ({layer.energy_ratio * 100:.1f}% note share)"):
                st.write(f"Instrument guess: {layer.estimated_instrument} (confidence {layer.confidence * 100:.0f}%)")
                st.audio(_read_bytes(layer.audio_path))
                st.write(f"Estimated notes: {layer.note_count}")
                if layer.midi_path and layer.musicxml_path:
                    c1, c2 = st.columns(2)
                    c1.download_button(
                        f"Layer MIDI",
                        data=_read_bytes(layer.midi_path),
                        file_name=layer.midi_path.name,
                        mime="audio/midi",
                        key=f"layerdl::{analysis_id}::{layer_idx}::midi",
                    )
                    c2.download_button(
                        f"Layer MusicXML",
                        data=_read_bytes(layer.musicxml_path),
                        file_name=layer.musicxml_path.name,
                        mime="application/vnd.recordare.musicxml+xml",
                        key=f"layerdl::{analysis_id}::{layer_idx}::xml",
                    )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Arrangement Workspace</div><div class="divider-line"></div>', unsafe_allow_html=True)
    st.caption("Disable layers, swap instruments, and shape each line with pitch, dynamics, and timing.")

    tracks = list_midi_tracks(analysis.full_midi_path)
    program_to_preset = {preset.gm_program: name for name, preset in INSTRUMENT_PRESETS.items()}

    _clear_track_widget_state(active_analysis_id=analysis_id)

    track_enabled: dict[int, bool] = {}
    track_to_preset_name: dict[int, str] = {}
    track_to_semitone_shift: dict[int, int] = {}
    track_to_velocity_scale: dict[int, float] = {}
    track_to_timing_shift_ms: dict[int, int] = {}

    for track in tracks:
        idx = int(track["track_index"])
        default_preset = program_to_preset.get(int(track["program"]), PRESET_NAMES[0])

        enabled_key = f"trackcfg::{analysis_id}::enabled::{idx}"
        preset_key = f"trackcfg::{analysis_id}::preset::{idx}"
        semitone_key = f"trackcfg::{analysis_id}::semitone::{idx}"
        velocity_key = f"trackcfg::{analysis_id}::velocity::{idx}"
        timing_key = f"trackcfg::{analysis_id}::timing::{idx}"

        if enabled_key not in st.session_state:
            st.session_state[enabled_key] = True
        if preset_key not in st.session_state:
            st.session_state[preset_key] = default_preset
        if semitone_key not in st.session_state:
            st.session_state[semitone_key] = 0
        if velocity_key not in st.session_state:
            st.session_state[velocity_key] = 100
        if timing_key not in st.session_state:
            st.session_state[timing_key] = 0

        st.markdown(f"**Layer {idx}** - {track['name']} - {track['note_count']} notes")
        c_on, c_inst, c_trans, c_vel, c_time = st.columns([0.9, 2.2, 1.0, 1.2, 1.1])

        enabled = c_on.checkbox("Use", key=enabled_key)
        selected_preset = c_inst.selectbox("Instrument", PRESET_NAMES, key=preset_key, label_visibility="collapsed")
        semitone_shift = c_trans.number_input("Semitone", -24, 24, key=semitone_key, step=1)
        velocity_percent = c_vel.slider("Velocity %", 25, 220, key=velocity_key, step=5)
        timing_shift_ms = c_time.number_input("Timing ms", -240, 240, key=timing_key, step=5)

        track_enabled[idx] = bool(enabled)
        track_to_preset_name[idx] = str(selected_preset)
        track_to_semitone_shift[idx] = int(semitone_shift)
        track_to_velocity_scale[idx] = float(velocity_percent) / 100.0
        track_to_timing_shift_ms[idx] = int(timing_shift_ms)

    render_config_signature = str(
        (
            tuple(sorted(track_enabled.items())),
            tuple(sorted(track_to_preset_name.items())),
            tuple(sorted(track_to_semitone_shift.items())),
            tuple(sorted((k, round(v, 4)) for k, v in track_to_velocity_scale.items())),
            tuple(sorted(track_to_timing_shift_ms.items())),
            bool(enable_sustain_pedal),
            bool(auto_soundfont),
            custom_soundfont.name if custom_soundfont is not None else "",
        )
    )

    if st.button("Render Arrangement", key=f"render::{analysis_id}", type="primary"):
        if run_dir is None:
            st.error("No run directory found. Regenerate the analysis.")
        else:
            arranged_midi = run_dir / "arranged.mid"
            arranged_xml = run_dir / "arranged.musicxml"
            arranged_wav = run_dir / "arranged.wav"

            try:
                soundfont_path: Path | None = None
                if custom_soundfont is not None:
                    sf_ext = Path(custom_soundfont.name).suffix.lower() or ".sf2"
                    soundfont_path = run_dir / f"custom_soundfont{sf_ext}"
                    soundfont_path.write_bytes(custom_soundfont.getvalue())
                elif auto_soundfont:
                    soundfont_path, downloaded_now = ensure_default_soundfont(ROOT)
                    if downloaded_now:
                        st.info(f"Downloaded {DEFAULT_SOUNDFONT_NAME}.")
                else:
                    st.error("Enable automatic SoundFont or upload a custom one.")

                if soundfont_path is not None:
                    out_midi, out_xml, out_wav = apply_instrument_map_and_render_preview(
                        source_midi_path=analysis.full_midi_path,
                        track_to_preset_name=track_to_preset_name,
                        out_midi_path=arranged_midi,
                        out_musicxml_path=arranged_xml,
                        out_preview_wav_path=arranged_wav,
                        soundfont_path=soundfont_path,
                        enable_sustain_pedal=enable_sustain_pedal,
                        track_enabled=track_enabled,
                        track_to_semitone_shift=track_to_semitone_shift,
                        track_to_velocity_scale=track_to_velocity_scale,
                        track_to_timing_shift_ms=track_to_timing_shift_ms,
                    )
                    st.session_state["arrangement"] = {
                        "analysis_id": analysis_id,
                        "config_signature": render_config_signature,
                        "midi": out_midi,
                        "xml": out_xml,
                        "wav": out_wav,
                        "pedal": enable_sustain_pedal,
                        "soundfont": soundfont_path,
                        "instrument_map": dict(track_to_preset_name),
                        "enabled_map": dict(track_enabled),
                    }
            except Exception as exc:
                st.exception(exc)

    arrangement = st.session_state.get("arrangement")
    if arrangement is not None and arrangement.get("analysis_id") == analysis_id:
        if arrangement.get("config_signature") != render_config_signature:
            st.info("Layer settings changed. Render again to update output files.")
        else:
            pedal_label = "ON" if arrangement["pedal"] else "OFF"
            st.success(f"Render ready - pedal {pedal_label} - {arrangement['soundfont'].name}")
            st.audio(_read_bytes(arrangement["wav"]))

            a1, a2, a3 = st.columns(3)
            a1.download_button(
                "Download Arranged MIDI",
                data=_read_bytes(arrangement["midi"]),
                file_name=arrangement["midi"].name,
                mime="audio/midi",
            )
            a2.download_button(
                "Download Arranged MusicXML",
                data=_read_bytes(arrangement["xml"]),
                file_name=arrangement["xml"].name,
                mime="application/vnd.recordare.musicxml+xml",
            )
            a3.download_button(
                "Download Arranged WAV",
                data=_read_bytes(arrangement["wav"]),
                file_name=arrangement["wav"].name,
                mime="audio/wav",
            )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Sheet Viewer</div><div class="divider-line"></div>', unsafe_allow_html=True)

    arrangement = st.session_state.get("arrangement")
    arrangement_is_fresh = (
        arrangement is not None
        and arrangement.get("analysis_id") == analysis_id
        and arrangement.get("config_signature") == render_config_signature
    )

    if arrangement_is_fresh:
        sheet_options: dict[str, Path] = {
            "Arranged Score (selected instruments)": arrangement["xml"],
            "Detected Full Mix Score": analysis.full_musicxml_path,
        }
    else:
        sheet_options = {"Detected Full Mix Score": analysis.full_musicxml_path}

    sheet_choice = st.radio(
        "Score source",
        options=list(sheet_options.keys()),
        horizontal=True,
        key=f"sheet_source::{analysis_id}::{1 if arrangement_is_fresh else 0}",
    )

    if arrangement_is_fresh and sheet_choice.startswith("Arranged"):
        instrument_map = arrangement.get("instrument_map", {})
        enabled_map = arrangement.get("enabled_map", {})
        mapped_rows = []
        for idx, instrument_name in sorted(instrument_map.items()):
            if not bool(enabled_map.get(idx, True)):
                continue
            mapped_rows.append(f"Layer {idx}: {instrument_name}")
        if mapped_rows:
            st.caption("Applied instruments - " + " | ".join(mapped_rows[:8]))

    selected_xml = sheet_options[sheet_choice]
    _render_musicxml_sheet(selected_xml, widget_id=f"{analysis_id}:{sheet_choice}:{selected_xml.name}")

    st.download_button(
        "Download Visible MusicXML",
        data=_read_bytes(selected_xml),
        file_name=selected_xml.name,
        mime="application/vnd.recordare.musicxml+xml",
        key=f"sheetdl::{analysis_id}::{sheet_choice}",
    )

    if not arrangement_is_fresh:
        st.info("Render arrangement to view the sheet with your currently selected instruments.")

    st.markdown("</div>", unsafe_allow_html=True)

st.caption(
    "Accuracy note: no current model is truly 100% accurate on arbitrary mixed audio, but this build uses multi-pass fusion + smoothing to reduce splits and stutter significantly."
)
