"""SoundFont management utilities."""

from __future__ import annotations

from pathlib import Path
import shutil
from urllib.request import urlretrieve

DEFAULT_SOUNDFONT_URL = (
    "https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf3"
)
DEFAULT_SOUNDFONT_NAME = "MuseScore_General.sf3"
SYSTEM_SOUNDFONT_PATHS = (
    Path("/usr/share/sounds/sf2/TimGM6mb.sf2"),
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
)


def ensure_default_soundfont(project_root: Path) -> tuple[Path, bool]:
    """Ensure a high-quality free SoundFont exists locally.

    Returns:
        (soundfont_path, downloaded_now)
    """
    sf_dir = project_root / "assets" / "soundfonts"
    sf_dir.mkdir(parents=True, exist_ok=True)

    sf_path = sf_dir / DEFAULT_SOUNDFONT_NAME
    if sf_path.exists() and sf_path.stat().st_size > 1_000_000:
        return sf_path, False

    # Docker/Linux installs include a compact GM SoundFont with FluidSynth.
    # Copy it into the persistent project volume so rendering works offline.
    for system_path in SYSTEM_SOUNDFONT_PATHS:
        if system_path.exists() and system_path.stat().st_size > 1_000_000:
            bundled_path = sf_dir / system_path.name
            if not bundled_path.exists():
                shutil.copyfile(system_path, bundled_path)
                return bundled_path, True
            return bundled_path, False

    urlretrieve(DEFAULT_SOUNDFONT_URL, sf_path)
    return sf_path, True
