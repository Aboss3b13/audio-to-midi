from __future__ import annotations

import hashlib
import io
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pretty_midi
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

st.set_page_config(
    page_title="ScoreFlow — Audio to sheet music",
    page_icon="🎼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root{--paper:#f7f6f1;--surface:#fff;--ink:#17201d;--muted:#66706c;--line:#e5e7e2;--lime:#b7f34a;--green:#183e32;--orange:#ff6b35}
    .stApp{background:var(--paper)} .block-container{max-width:1240px;padding:1.5rem 2rem 4rem}
    html,body,[class*="css"],p,div,label,span,button,input{font-family:'DM Sans',sans-serif} h1,h2,h3{font-family:'Manrope',sans-serif!important;color:var(--ink)} h1{letter-spacing:-.05em}
    [data-testid="stSidebar"]{background:#14271f;border-right:0}[data-testid="stSidebar"]>div{padding-top:1.1rem}[data-testid="stSidebar"] *{color:#eef4ef}[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,.12)}
    [data-testid="stSidebar"] [data-baseweb="slider"] *{color:#b7f34a}[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]{background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.18)}
    .brand{display:flex;align-items:center;gap:.72rem;margin-bottom:1.5rem}.brand-mark{width:2.2rem;height:2.2rem;display:grid;place-items:center;border-radius:10px;background:var(--lime);color:#14271f;font:800 1.1rem 'Manrope';transform:rotate(-4deg)}
    .brand-name{color:white;font:800 1.1rem 'Manrope';letter-spacing:-.03em}.brand-beta{color:#9caea7;font-size:.66rem;text-transform:uppercase;letter-spacing:.13em}
    .hero{position:relative;overflow:hidden;min-height:285px;border-radius:28px;padding:2.8rem 3rem;background:#183e32;box-shadow:0 18px 50px rgba(23,32,29,.12);margin-bottom:1.6rem}
    .hero:after{content:'♪';position:absolute;right:4%;top:-28%;color:rgba(183,243,74,.14);font:800 26rem 'Manrope';transform:rotate(8deg);line-height:1}.eyebrow{display:inline-flex;align-items:center;gap:.45rem;padding:.38rem .7rem;border-radius:99px;background:rgba(255,255,255,.1);color:#dce9e3;font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
    .eyebrow-dot{width:7px;height:7px;border-radius:50%;background:var(--lime)}.hero h1{color:white;font-size:clamp(2.5rem,5vw,4.7rem);line-height:.94;margin:.9rem 0 .8rem;max-width:760px}.hero h1 span{color:var(--lime);font-family:inherit}.hero p{color:#c9d6d1;font-size:1.05rem;max-width:650px;margin:0;line-height:1.65}
    .hero-chips{position:relative;z-index:2;display:flex;gap:.55rem;flex-wrap:wrap;margin-top:1.3rem}.hero-chip{color:white;font-size:.72rem;padding:.38rem .7rem;border:1px solid rgba(255,255,255,.18);border-radius:99px}
    .step-label{display:flex;align-items:center;gap:.65rem;margin:1.7rem 0 .75rem}.step-number{width:1.8rem;height:1.8rem;display:grid;place-items:center;border-radius:50%;color:#17392f;background:var(--lime);font-weight:800;font-size:.78rem}.step-title{font:800 1.05rem 'Manrope';color:var(--ink)}.step-copy{color:var(--muted);font-size:.83rem;margin-left:auto}
    .upload-shell{border:1px solid var(--line);background:var(--surface);border-radius:22px;padding:1.2rem 1.35rem;box-shadow:0 8px 28px rgba(23,32,29,.05)}[data-testid="stFileUploaderDropzone"]{border:1.5px dashed #bdc5bf;border-radius:16px;background:#fafbf8}
    .mode-note{background:#eef3e9;border-left:3px solid #5a7f33;border-radius:0 10px 10px 0;padding:.75rem .9rem;color:#405247!important;font-size:.8rem}.ready-card{background:#ecf7d9;border:1px solid #cfe9a5;border-radius:14px;padding:.85rem 1rem;color:#29421c}
    .success-banner{display:flex;align-items:center;gap:.85rem;padding:1rem 1.15rem;margin:1.1rem 0;background:#e8f6de;border:1px solid #c9e9b4;border-radius:16px;color:#25401d}.success-icon{width:2rem;height:2rem;display:grid;place-items:center;border-radius:50%;background:#b7f34a;font-weight:900}
    .metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:.7rem 0 1.2rem}.metric-card{background:white;border:1px solid var(--line);border-radius:16px;padding:1rem 1.05rem}.metric-value{font:800 1.65rem 'Manrope';color:var(--ink);letter-spacing:-.04em}.metric-label{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;margin-top:.15rem}
    .layer-card{background:white;border:1px solid var(--line);border-radius:17px;padding:1rem 1.1rem;margin:.55rem 0}.layer-top{display:flex;align-items:center;justify-content:space-between;gap:1rem}.layer-name{font:700 .98rem 'Manrope';color:var(--ink)}.layer-meta{color:var(--muted);font-size:.77rem;margin-top:.2rem}.confidence{padding:.28rem .55rem;border-radius:99px;background:#eef3e9;color:#456128;font-size:.7rem;font-weight:700;white-space:nowrap}
    .empty-state{text-align:center;padding:3.5rem 1rem;color:var(--muted)}.empty-icon{font-size:2.3rem;filter:grayscale(1);opacity:.65;margin-bottom:.6rem}.fine-print{color:#9caea7!important;font-size:.73rem;line-height:1.5}
    .stButton>button,.stDownloadButton>button{min-height:2.75rem;border-radius:12px;font-weight:700;transition:.16s ease}.stButton>button[kind="primary"]{background:var(--orange);border-color:var(--orange);color:white;box-shadow:0 7px 18px rgba(255,107,53,.2)}.stButton>button[kind="primary"]:hover{background:#ee5926;border-color:#ee5926;transform:translateY(-1px)}
    .stDownloadButton>button{background:white;border:1px solid #d9ddd8;color:var(--ink)}.stDownloadButton>button:hover{border-color:#79966d;color:#244537}.stTabs [data-baseweb="tab-list"]{gap:.2rem;border-bottom:1px solid var(--line)}.stTabs [data-baseweb="tab"]{font-weight:700;color:var(--muted);padding:.2rem .9rem .7rem}.stTabs [aria-selected="true"]{color:var(--green)!important}
    [data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:14px;padding:.75rem}[data-testid="stExpander"]{background:white;border:1px solid var(--line);border-radius:14px}
    @media(max-width:800px){.block-container{padding:1rem .8rem 3rem}.hero{padding:2rem 1.3rem;min-height:0}.hero:after{display:none}.metric-grid{grid-template-columns:repeat(2,1fr)}.step-copy{display:none}}
    </style>
    """,
    unsafe_allow_html=True,
)


def _timestamp_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _audio_mime(path: Path) -> str:
    return {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".flac": "audio/flac"}.get(path.suffix.lower(), "audio/wav")


def _source_signature(name: str, data: bytes) -> str:
    return f"{name.lower()}::{len(data)}::{hashlib.sha1(data).hexdigest()[:12]}"


def _format_time(seconds: float) -> str:
    minutes, secs = divmod(max(0, int(round(seconds))), 60)
    return f"{minutes}:{secs:02d}"


def _midi_stats(midi_path: Path) -> dict[str, str | int | float]:
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    _, tempi = midi.get_tempo_changes()
    tempo = int(round(float(tempi[0]))) if len(tempi) else 120
    pitches = [n.pitch for inst in midi.instruments for n in inst.notes]
    pitch_range = "—"
    if pitches:
        pitch_range = f"{pretty_midi.note_number_to_name(min(pitches))}–{pretty_midi.note_number_to_name(max(pitches))}"
    return {"duration": float(midi.get_end_time()), "tempo": tempo, "range": pitch_range, "tracks": len(midi.instruments)}


def _sanitize_musicxml(xml_text: str) -> str:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return xml_text
    for time_node in root.findall(".//time"):
        beats = time_node.find("beats")
        beat_type = time_node.find("beat-type")
        if beats is None:
            beats = ET.SubElement(time_node, "beats")
        if beat_type is None:
            beat_type = ET.SubElement(time_node, "beat-type")
        beats.text = (beats.text or "4").strip() or "4"
        beat_type.text = (beat_type.text or "4").strip() or "4"
    return ET.tostring(root, encoding="unicode")


def _score_viewer(xml_path: Path, widget_id: str) -> tuple[list[str], int]:
    """Render MusicXML and return its SVG pages and selected page."""
    try:
        import verovio

        toolkit = verovio.toolkit()
        toolkit.setOptions({"scale": 38, "pageWidth": 2100, "pageHeight": 2970, "header": "none", "footer": "none", "breaks": "auto", "svgViewBox": True})
        loaded = bool(toolkit.loadFile(str(xml_path)))
        if not loaded or int(toolkit.getPageCount() or 0) < 1:
            loaded = bool(toolkit.loadData(_sanitize_musicxml(xml_path.read_text(encoding="utf-8", errors="ignore"))))
        page_count = int(toolkit.getPageCount() or 0)
        if not loaded or page_count < 1:
            raise RuntimeError("The score renderer could not read this MusicXML file.")
        pages = [toolkit.renderToSVG(i) for i in range(1, page_count + 1)]
        page = st.select_slider("Score page", options=list(range(1, page_count + 1)), value=1, key=f"page::{widget_id}")
        st.markdown(f'<div style="max-height:760px;overflow:auto;background:white;border:1px solid #e5e7e2;border-radius:16px;padding:12px">{pages[page - 1]}</div>', unsafe_allow_html=True)
        st.caption(f"Page {page} of {page_count} · Download SVG for a print-ready vector page.")
        return pages, page
    except Exception as exc:
        st.warning("The in-app score preview is unavailable, but your MusicXML download is ready.")
        with st.expander("Viewer details"):
            st.code(str(exc))
        return [], 1


def _project_bundle(analysis, arrangement: dict | None) -> bytes:
    files: list[Path] = [analysis.source_audio_path, analysis.full_midi_path, analysis.full_musicxml_path]
    for layer in analysis.layers:
        files.append(layer.audio_path)
        files.extend(path for path in [layer.midi_path, layer.musicxml_path] if path)
    if arrangement:
        files.extend([arrangement["midi"], arrangement["xml"], arrangement["wav"]])
    buffer, seen = io.BytesIO(), set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in map(Path, files):
            if path.exists() and path not in seen:
                archive.write(path, arcname=path.name)
                seen.add(path)
        archive.writestr("README.txt", "ScoreFlow project export\n\nOpen .musicxml in MuseScore, Dorico, Sibelius, or Finale.\nOpen .mid in any DAW or MIDI player.\n")
    return buffer.getvalue()


def _reset() -> None:
    for key in list(st.session_state):
        if key.startswith("track::") or key in {"analysis", "run_dir", "analysis_id", "arrangement", "input_signature"}:
            st.session_state.pop(key, None)


with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">S</div><div><div class="brand-name">ScoreFlow</div><div class="brand-beta">Audio intelligence</div></div></div>', unsafe_allow_html=True)
    st.caption("WORKSPACE MODE")
    mode = st.radio("Workspace mode", ["Simple", "Advanced"], horizontal=True, label_visibility="collapsed")
    note = "Smart defaults handle layer detection, timing cleanup, and score generation." if mode == "Simple" else "Tune detection and edit each transcribed layer independently."
    st.markdown(f'<div class="mode-note">{note}</div>', unsafe_allow_html=True)
    st.divider()
    if mode == "Advanced":
        st.caption("TRANSCRIPTION")
        detection_method = st.selectbox("Layer engine", ["Stem-guided replica", "Note clustering", "Single score"])
        export_layers = st.toggle("Create individual layer files", value=True)
        target_layer_count = st.slider("Target layers", 1, 8, 4)
        min_layer_note_ratio = st.slider("Minimum layer share", 0.02, 0.25, 0.06, 0.01)
        with st.expander("Model sensitivity"):
            onset_threshold = st.slider("Onset threshold", 0.35, 0.85, 0.58, 0.01)
            frame_threshold = st.slider("Frame threshold", 0.08, 0.50, 0.23, 0.01)
            minimum_note_length_ms = st.slider("Model min. note (ms)", 60, 520, 180, 5)
            min_output_note_length_ms = st.slider("Final min. note (ms)", 40, 380, 115, 5)
            merge_gap_ms = st.slider("Merge gap (ms)", 20, 350, 130, 5)
            legato_extension_ms = st.slider("Legato extension (ms)", 0, 260, 70, 5)
            flicker_merge_gap_ms = st.slider("Pitch flicker gap (ms)", 10, 120, 45, 5)
            sustain_boost = st.slider("Sustain fusion", 0.02, 0.20, 0.08, 0.01)
    else:
        detection_method, export_layers, target_layer_count, min_layer_note_ratio = "Stem-guided replica", True, 4, 0.06
        onset_threshold, frame_threshold = 0.58, 0.23
        minimum_note_length_ms, min_output_note_length_ms = 180, 115
        merge_gap_ms, legato_extension_ms, flicker_merge_gap_ms, sustain_boost = 130, 70, 45, 0.08
    st.divider()
    st.caption("SESSION")
    if st.button("Start a new project", use_container_width=True):
        _reset()
        st.rerun()
    st.markdown('<p class="fine-print">Files are processed locally and saved only in this project workspace.</p>', unsafe_allow_html=True)


st.markdown(
    """
    <section class="hero">
      <div class="eyebrow"><span class="eyebrow-dot"></span> AI-assisted transcription studio</div>
      <h1>Turn sound into<br><span>something playable.</span></h1>
      <p>Upload a recording. ScoreFlow finds the notes, separates musical layers, and gives you clean sheet music and MIDI to keep.</p>
      <div class="hero-chips"><span class="hero-chip">MP3 · WAV · M4A · FLAC</span><span class="hero-chip">Layer detection</span><span class="hero-chip">MIDI + MusicXML</span></div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="step-label"><span class="step-number">1</span><span class="step-title">Add your audio</span><span class="step-copy">Upload a file or record an idea</span></div>', unsafe_allow_html=True)
st.markdown('<div class="upload-shell">', unsafe_allow_html=True)
upload_tab, record_tab = st.tabs(["Upload file", "Record now"])
uploaded_file = recorded_audio = None
with upload_tab:
    uploaded_file = st.file_uploader("Drop a recording here", type=["mp3", "wav", "m4a", "flac"], help="For best results, use a clear recording with limited background noise.")
with record_tab:
    recorded_audio = st.audio_input("Record from your microphone")
st.markdown("</div>", unsafe_allow_html=True)

source_name = ""
source_bytes: bytes | None = None
if recorded_audio is not None:
    source_name, source_bytes = "recording.wav", recorded_audio.getvalue()
elif uploaded_file is not None:
    source_name, source_bytes = uploaded_file.name, uploaded_file.getvalue()

if source_bytes:
    st.audio(source_bytes)
    st.markdown(f'<div class="ready-card"><b>Ready to transcribe</b> · {source_name} · {len(source_bytes) / 1_048_576:.1f} MB</div>', unsafe_allow_html=True)
    signature = _source_signature(source_name, source_bytes)
    if st.session_state.get("input_signature") and st.session_state.get("input_signature") != signature:
        st.info("This is a new recording. Transcribe it to replace the current results.")

st.markdown('<div class="step-label"><span class="step-number">2</span><span class="step-title">Create the score</span><span class="step-copy">Pitch detection · layer separation · notation</span></div>', unsafe_allow_html=True)
transcribe = st.button("Transcribe audio", type="primary", use_container_width=True, disabled=source_bytes is None)

if transcribe and source_bytes is not None:
    run_id = _timestamp_id()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    extension = Path(source_name).suffix.lower() or ".wav"
    source_path = run_dir / f"source{extension}"
    source_path.write_bytes(source_bytes)
    detect_layers = detection_method != "Single score"
    replica_mode = detection_method == "Stem-guided replica"
    try:
        with st.status("Listening closely…", expanded=True) as status:
            st.write("Reading the recording and finding note events")
            st.write("Separating voices and cleaning timing")
            analysis = analyze_audio(
                audio_path=source_path, output_root=run_dir, detect_layers=detect_layers,
                transcribe_detected_layers=bool(export_layers), replica_mode=replica_mode,
                min_layer_energy_ratio=float(min_layer_note_ratio), target_layer_count=int(target_layer_count) if detect_layers else None,
                onset_threshold=float(onset_threshold), frame_threshold=float(frame_threshold),
                minimum_note_length_ms=float(minimum_note_length_ms), min_output_note_length_ms=float(min_output_note_length_ms),
                merge_gap_ms=float(merge_gap_ms), legato_extension_ms=float(legato_extension_ms),
                flicker_merge_gap_ms=float(flicker_merge_gap_ms), sustain_boost=float(sustain_boost),
            )
            status.update(label="Your score is ready", state="complete", expanded=False)
        st.session_state.update(analysis=analysis, run_dir=run_dir, analysis_id=run_id, input_signature=_source_signature(source_name, source_bytes))
        st.session_state.pop("arrangement", None)
    except Exception as exc:
        st.error("Transcription could not be completed. Try a shorter or clearer audio file, or adjust sensitivity in Advanced mode.")
        with st.expander("Technical details"):
            st.exception(exc)

analysis = st.session_state.get("analysis")
run_dir: Path | None = st.session_state.get("run_dir")
analysis_id = str(st.session_state.get("analysis_id", "none"))
if analysis is None:
    st.markdown('<div class="empty-state"><div class="empty-icon">♬</div><b>Your results will appear here</b><br><span>Start with a recording above.</span></div>', unsafe_allow_html=True)
    st.stop()

stats = _midi_stats(analysis.full_midi_path)
st.markdown('<div class="success-banner"><span class="success-icon">✓</span><div><b>Transcription complete</b><br><span>Your editable score, MIDI, and detected layers are ready.</span></div></div>', unsafe_allow_html=True)
st.markdown('<div class="step-label"><span class="step-number">3</span><span class="step-title">Explore and export</span><span class="step-copy">Review, arrange, and download</span></div>', unsafe_allow_html=True)
st.markdown(f"""<div class="metric-grid">
<div class="metric-card"><div class="metric-value">{analysis.full_note_count}</div><div class="metric-label">Notes found</div></div>
<div class="metric-card"><div class="metric-value">{len(analysis.layers)}</div><div class="metric-label">Layers</div></div>
<div class="metric-card"><div class="metric-value">{_format_time(float(stats['duration']))}</div><div class="metric-label">Duration</div></div>
<div class="metric-card"><div class="metric-value">{stats['range']}</div><div class="metric-label">Pitch range</div></div></div>""", unsafe_allow_html=True)

tab_names = ["Overview", "Sheet music", "Layers", "Downloads"]
if mode == "Advanced":
    tab_names[3:3] = ["Arrange", "Note data"]
tabs = st.tabs(tab_names)
tab_map = dict(zip(tab_names, tabs))

with tab_map["Overview"]:
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.subheader("Original recording")
        st.audio(_read_bytes(analysis.source_audio_path))
        st.caption(f"Source · {analysis.source_audio_path.name}")
        st.subheader("What ScoreFlow heard")
        if analysis.layers:
            for layer in analysis.layers:
                st.markdown(f'<div class="layer-card"><div class="layer-top"><div><div class="layer-name">{layer.name}</div><div class="layer-meta">{layer.note_count} notes · {layer.energy_ratio * 100:.0f}% of arrangement</div></div><span class="confidence">{layer.confidence * 100:.0f}% confidence</span></div></div>', unsafe_allow_html=True)
        else:
            st.info("This transcription was created as a single combined score.")
    with right:
        st.subheader("Quick export")
        st.download_button("Download MIDI", _read_bytes(analysis.full_midi_path), "scoreflow-transcription.mid", "audio/midi", use_container_width=True)
        st.download_button("Download sheet music", _read_bytes(analysis.full_musicxml_path), "scoreflow-sheet.musicxml", "application/vnd.recordare.musicxml+xml", use_container_width=True)
        st.info(f"Estimated tempo: {stats['tempo']} BPM · {stats['tracks']} score part(s)")
        st.caption("MusicXML opens in MuseScore, Dorico, Sibelius, Finale, and most notation apps.")

with tab_map["Sheet music"]:
    st.subheader("Your score")
    st.caption("Preview the notation, then download the editable MusicXML or a vector score page.")
    score_pages, selected_page = _score_viewer(analysis.full_musicxml_path, analysis_id)
    c1, c2 = st.columns(2)
    c1.download_button("Download editable MusicXML", _read_bytes(analysis.full_musicxml_path), "scoreflow-sheet.musicxml", "application/vnd.recordare.musicxml+xml", use_container_width=True)
    if score_pages:
        c2.download_button("Download current page as SVG", score_pages[selected_page - 1].encode("utf-8"), f"scoreflow-sheet-page-{selected_page}.svg", "image/svg+xml", use_container_width=True)

with tab_map["Layers"]:
    st.subheader("Detected musical layers")
    st.caption("Audition each voice on its own and take the isolated notation or MIDI into your own tools.")
    if not analysis.layers:
        st.info("No individual layers were exported. Choose a layer engine in Advanced mode and transcribe again.")
    for idx, layer in enumerate(analysis.layers):
        with st.expander(f"{layer.name} · {layer.note_count} notes", expanded=idx == 0):
            info, audio = st.columns([1, 1.6])
            with info:
                st.write(f"**Instrument estimate**  \n{layer.estimated_instrument}")
                st.write(f"**Confidence**  \n{layer.confidence * 100:.0f}%")
                st.write(f"**Arrangement share**  \n{layer.energy_ratio * 100:.1f}%")
            with audio:
                st.audio(_read_bytes(layer.audio_path))
            if layer.midi_path and layer.musicxml_path:
                d1, d2 = st.columns(2)
                d1.download_button("Layer MIDI", _read_bytes(layer.midi_path), f"layer-{idx + 1}.mid", "audio/midi", key=f"layer-midi-{analysis_id}-{idx}", use_container_width=True)
                d2.download_button("Layer sheet", _read_bytes(layer.musicxml_path), f"layer-{idx + 1}.musicxml", "application/vnd.recordare.musicxml+xml", key=f"layer-xml-{analysis_id}-{idx}", use_container_width=True)

if "Arrange" in tab_map:
    with tab_map["Arrange"]:
        st.subheader("Arrangement studio")
        st.caption("Choose which parts to keep, change instruments, and shape pitch, dynamics, or timing before rendering a new version.")
        tracks = list_midi_tracks(analysis.full_midi_path)
        program_names = {preset.gm_program: name for name, preset in INSTRUMENT_PRESETS.items()}
        enabled_map: dict[int, bool] = {}
        preset_map: dict[int, str] = {}
        transpose_map: dict[int, int] = {}
        velocity_map: dict[int, float] = {}
        timing_map: dict[int, int] = {}
        for track in tracks:
            idx = int(track["track_index"])
            default_preset = program_names.get(int(track["program"]), "Acoustic Grand Piano")
            with st.expander(f"Part {idx + 1} · {track['name']} · {track['note_count']} notes", expanded=idx == 0):
                use = st.toggle("Include this part", value=True, key=f"track::{analysis_id}::{idx}::use")
                c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
                preset = c1.selectbox("Instrument", PRESET_NAMES, index=PRESET_NAMES.index(default_preset), key=f"track::{analysis_id}::{idx}::preset")
                transpose = c2.number_input("Transpose", -24, 24, 0, key=f"track::{analysis_id}::{idx}::transpose")
                velocity = c3.number_input("Volume %", 25, 220, 100, step=5, key=f"track::{analysis_id}::{idx}::velocity")
                timing = c4.number_input("Timing ms", -240, 240, 0, step=5, key=f"track::{analysis_id}::{idx}::timing")
            enabled_map[idx], preset_map[idx] = bool(use), str(preset)
            transpose_map[idx], velocity_map[idx], timing_map[idx] = int(transpose), float(velocity) / 100, int(timing)

        rc1, rc2 = st.columns(2)
        sustain = rc1.toggle("Add sustain pedal", value=False)
        custom_soundfont = rc2.file_uploader("Optional SoundFont", type=["sf2", "sf3"])
        config_signature = repr((enabled_map, preset_map, transpose_map, velocity_map, timing_map, sustain, custom_soundfont.name if custom_soundfont else ""))
        if st.button("Render arrangement", type="primary", use_container_width=True):
            if not any(enabled_map.values()):
                st.error("Include at least one part before rendering.")
            elif run_dir is None:
                st.error("The project folder is unavailable. Transcribe the audio again.")
            else:
                try:
                    if custom_soundfont:
                        suffix = Path(custom_soundfont.name).suffix.lower() or ".sf2"
                        soundfont_path = run_dir / f"custom-soundfont{suffix}"
                        soundfont_path.write_bytes(custom_soundfont.getvalue())
                    else:
                        soundfont_path, downloaded = ensure_default_soundfont(ROOT)
                        if downloaded:
                            st.toast(f"Downloaded {DEFAULT_SOUNDFONT_NAME}")
                    with st.spinner("Rendering your arrangement…"):
                        midi_path, xml_path, wav_path = apply_instrument_map_and_render_preview(
                            source_midi_path=analysis.full_midi_path, track_to_preset_name=preset_map,
                            out_midi_path=run_dir / "arranged.mid", out_musicxml_path=run_dir / "arranged.musicxml",
                            out_preview_wav_path=run_dir / "arranged.wav", soundfont_path=soundfont_path,
                            enable_sustain_pedal=bool(sustain), track_enabled=enabled_map,
                            track_to_semitone_shift=transpose_map, track_to_velocity_scale=velocity_map,
                            track_to_timing_shift_ms=timing_map,
                        )
                    st.session_state["arrangement"] = {"analysis_id": analysis_id, "signature": config_signature, "midi": midi_path, "xml": xml_path, "wav": wav_path}
                except Exception as exc:
                    st.error("The arrangement could not be rendered. FluidSynth must be available for audio previews.")
                    with st.expander("Technical details"):
                        st.exception(exc)
        arrangement = st.session_state.get("arrangement")
        if arrangement and arrangement.get("analysis_id") == analysis_id:
            if arrangement.get("signature") != config_signature:
                st.info("Your controls changed. Render again to update the files.")
            else:
                st.success("Arrangement ready")
                st.audio(_read_bytes(arrangement["wav"]))
                a1, a2, a3 = st.columns(3)
                a1.download_button("Arranged MIDI", _read_bytes(arrangement["midi"]), "scoreflow-arranged.mid", "audio/midi", use_container_width=True)
                a2.download_button("Arranged sheet", _read_bytes(arrangement["xml"]), "scoreflow-arranged.musicxml", "application/vnd.recordare.musicxml+xml", use_container_width=True)
                a3.download_button("Audio preview", _read_bytes(arrangement["wav"]), "scoreflow-arranged.wav", "audio/wav", use_container_width=True)

if "Note data" in tab_map:
    with tab_map["Note data"]:
        st.subheader("Detected note events")
        notes_df = pd.DataFrame(midi_notes_table(analysis.full_midi_path))
        if notes_df.empty:
            st.info("No note events were found.")
        else:
            st.dataframe(notes_df, use_container_width=True, height=480, hide_index=True)
            st.download_button("Download note table (CSV)", notes_df.to_csv(index=False).encode("utf-8"), "scoreflow-notes.csv", "text/csv")

with tab_map["Downloads"]:
    st.subheader("Take the whole project")
    st.caption("Everything is organized into one portable package, including individual layer files when available.")
    arrangement = st.session_state.get("arrangement")
    if arrangement and arrangement.get("analysis_id") != analysis_id:
        arrangement = None
    bundle = _project_bundle(analysis, arrangement)
    st.download_button("Download complete project (.zip)", bundle, "scoreflow-project.zip", "application/zip", type="primary", use_container_width=True)
    st.markdown("**Included formats**")
    st.markdown("- **MusicXML** — editable sheet music for notation software\n- **MIDI** — notes, timing, and instruments for a DAW\n- **WAV/audio** — original and isolated layer previews\n- **CSV** — available in Advanced mode for detailed note analysis")
    st.caption("Tip: Import MusicXML into MuseScore to polish engraving and export a final PDF.")
