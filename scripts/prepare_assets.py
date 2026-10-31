"""Converts raw backgrounds and music into the ready-to-use library.

Raw (local only, not in git):  assets/backgrounds/<category>/*, assets/music/<mood>/*
Ready (committed to the private media repo): media/library/backgrounds/<category>/*.jpg (1080x1350)
                               media/library/music/<mood>/*.mp3 (60s, loudness-normalized)
                               media/library/index.json

Run after adding new files: python -m scripts.prepare_assets
"""
import json
import re
import subprocess

from PIL import Image, ImageOps, ImageStat

from engine.config import ROOT

RAW_BG = ROOT / "assets" / "backgrounds"
RAW_MUSIC = ROOT / "assets" / "music"
LIB = ROOT / "media" / "library"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a"}
SEGMENT_SECONDS = 60


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def prepare_backgrounds() -> dict:
    index = {}
    for cat_dir in sorted(p for p in RAW_BG.iterdir() if p.is_dir()):
        out_dir = LIB / "backgrounds" / cat_dir.name          # 1080x1350 for carousels
        out_v = LIB / "backgrounds_v" / cat_dir.name          # 1080x1920 for video scenes
        out_dir.mkdir(parents=True, exist_ok=True)
        out_v.mkdir(parents=True, exist_ok=True)
        entries = []
        for src in sorted(cat_dir.iterdir()):
            if src.suffix.lower() not in IMAGE_EXT:
                continue
            name = f"{slug(src.stem)}.jpg"
            original = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
            img = ImageOps.fit(original, (1080, 1350), Image.LANCZOS, centering=(0.5, 0.45))
            if not (out_dir / name).exists():
                img.save(out_dir / name, "JPEG", quality=88, optimize=True)
            if not (out_v / name).exists():
                vertical = ImageOps.fit(original, (1080, 1920), Image.LANCZOS, centering=(0.5, 0.5))
                vertical.save(out_v / name, "JPEG", quality=88, optimize=True)
            brightness = round(ImageStat.Stat(img.convert("L")).mean[0] / 255, 2)
            entries.append({
                "file": f"backgrounds/{cat_dir.name}/{name}",
                "file_v": f"backgrounds_v/{cat_dir.name}/{name}",
                "brightness": brightness,
            })
        index[cat_dir.name] = entries
        print(f"backgrounds/{cat_dir.name}: {len(entries)}")
    return index


def duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def prepare_music() -> dict:
    index = {}
    for mood_dir in sorted(p for p in RAW_MUSIC.iterdir() if p.is_dir()):
        out_dir = LIB / "music" / mood_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        entries = []
        for src in sorted(mood_dir.iterdir()):
            if src.suffix.lower() not in AUDIO_EXT:
                continue
            dest = out_dir / f"{slug(src.stem)}.mp3"
            if not dest.exists():
                total = duration(src)
                # Skip the intro: start ~15% in, but keep a full segment
                start = max(0.0, min(total * 0.15, total - SEGMENT_SECONDS))
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.1f}", "-t", str(SEGMENT_SECONDS),
                     "-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                     "-ac", "2", "-ar", "44100", "-b:a", "128k", str(dest)],
                    check=True,
                )
            # Raw file names are "Title - Artist"
            title, _, artist = src.stem.partition(" - ")
            entries.append({"file": f"music/{mood_dir.name}/{dest.name}", "title": title.strip(), "artist": artist.strip()})
        index[mood_dir.name] = entries
        print(f"music/{mood_dir.name}: {len(entries)}")
    return index


if __name__ == "__main__":
    index = {"backgrounds": prepare_backgrounds(), "music": prepare_music()}
    (LIB / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print("wrote media/library/index.json")
