from pathlib import Path

# Define absolute path to the output directory
TRAILMIXER_ROOT = Path(__file__).resolve().parent.parent

UPLOAD_DIR = TRAILMIXER_ROOT / "upload"
UPLOAD_DIR.mkdir(exist_ok=True)

PROCESSED_DIR = TRAILMIXER_ROOT / "processed"
PROCESSED_DIR.mkdir(exist_ok=True)

VIDEOS_DIR = TRAILMIXER_ROOT / "videos"
VIDEOS_DIR.mkdir(exist_ok=True)

MUSIC_DIR = TRAILMIXER_ROOT / "music"
MUSIC_DIR.mkdir(exist_ok=True)

STITCHED_DIR = TRAILMIXER_ROOT / "stitched"
STITCHED_DIR.mkdir(exist_ok=True)

TEMP_DIR = TRAILMIXER_ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)

CROPPED_DIR = TRAILMIXER_ROOT / "cropped"
CROPPED_DIR.mkdir(exist_ok=True)