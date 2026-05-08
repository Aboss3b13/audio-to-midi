"""Music Identifier package."""

from .pipeline import AnalysisResult, LayerResult, analyze_audio
from .playback import apply_instrument_map_and_render_preview, list_midi_tracks
from .instruments import INSTRUMENT_PRESETS, PRESET_NAMES
from .soundfont import DEFAULT_SOUNDFONT_NAME, ensure_default_soundfont

__all__ = [
    "AnalysisResult",
    "LayerResult",
    "analyze_audio",
    "apply_instrument_map_and_render_preview",
    "list_midi_tracks",
    "INSTRUMENT_PRESETS",
    "PRESET_NAMES",
    "ensure_default_soundfont",
    "DEFAULT_SOUNDFONT_NAME",
]
