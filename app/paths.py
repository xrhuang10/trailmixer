from pathlib import Path

# Define absolute path to the output directory
TRAILMIXER_ROOT = Path(__file__).resolve().parent.parent

UPLOAD_DIR = TRAILMIXER_ROOT / "upload"
UPLOAD_DIR.mkdir(exist_ok=True)

OUTPUT_DIR = TRAILMIXER_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

VIDEO_DIR = TRAILMIXER_ROOT / "video"
VIDEO_DIR.mkdir(exist_ok=True)

MUSIC_DIR = TRAILMIXER_ROOT / "music"
MUSIC_DIR.mkdir(exist_ok=True)