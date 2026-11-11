"""The illustrated presenter used in animated Reels: one PNG per pose, swapped with a squash-and-bounce.

Poses live in the private media repo at media/library/characters/<account>/ (if an account has its own
character) or media/library/characters/shared/. Add a new pose by dropping <pose>.png there.
"""
from pathlib import Path

CHARACTERS = Path(__file__).resolve().parents[2] / "media" / "library" / "characters"
# Script gestures -> pose files
POSE_FOR = {"point": "point_side", "explain": "explain", "shrug": "shrug", "mouth": "shocked", "thumbs": "thumbs_up",
            "celebrate": "celebrate", "think": "thinking", "facepalm": "facepalm", "phone": "phone",
            "point_up": "point_up", "wink": "wink_thumbs", "neutral": "neutral"}


def pose_files(account_id: str) -> dict[str, Path]:
    """pose name -> PNG, from the account's own folder if it has one, else the shared character."""
    for folder in (CHARACTERS / account_id, CHARACTERS / "shared"):
        files = {f.stem: f for f in sorted(folder.glob("*.png"))} if folder.is_dir() else {}
        if files:
            return files
    raise FileNotFoundError(f"no presenter poses in {CHARACTERS} (is the media repo checked out?)")


def assets(poses: dict[str, Path]) -> dict[str, Path]:
    """Files to copy into the HyperFrames project."""
    return {f"pose_{name}.png": f for name, f in poses.items()}


def html(poses: dict[str, Path]) -> str:
    imgs = "".join(f'<img id="p-{name}" class="pose" src="assets/pose_{name}.png">' for name in poses)
    return f'<div id="presenter-in"><div id="presenter-bob"><div id="presenter">{imgs}</div></div></div>'


def css(right: int = -40, width: int = 700, left: int | None = None) -> str:
    """Placement (bottom-anchored) plus the pose stacking rules. Plain CSS, not an f-string template."""
    side = f"left: {left}px;" if left is not None else f"right: {right}px;"
    return (f"#presenter-in {{ position: absolute; {side} bottom: 0; width: {width}px; height: {round(width * 1.01)}px; }}\n"
            "#presenter-bob, #presenter { position: absolute; inset: 0; }\n"
            ".pose { position: absolute; left: 0; bottom: 0; width: 100%; height: 100%; object-fit: contain; "
            "object-position: bottom; opacity: 0; }\n")


def pose(name: str, at: float, poses: dict[str, Path]) -> list[str]:
    """Swap to the pose for this gesture (or pose name) with a quick squash-and-bounce."""
    p = POSE_FOR.get(name, name)
    if p not in poses:
        p = "explain" if "explain" in poses else next(iter(poses))
    at = round(at, 2)
    return [f'tl.set(".pose", {{opacity: 0}}, {at});', f'tl.set("#p-{p}", {{opacity: 1}}, {at});',
            f'tl.fromTo("#presenter", {{scaleX: 1.06, scaleY: 0.92}}, {{scaleX: 1, scaleY: 1, duration: 0.35, '
            f'ease: "back.out(3)", transformOrigin: "50% 100%"}}, {at});']


def enter(at: float = 0) -> list[str]:
    return [f'tl.fromTo("#presenter-in", {{y: 700}}, {{y: 0, duration: 0.5, ease: "back.out(1.6)"}}, {at});']


def bob(start: float, end: float) -> list[str]:
    """Gentle bob, e.g. while the voice speaks."""
    return [f'tl.fromTo("#presenter-bob", {{y: 0}}, {{y: -10, duration: 0.22, repeat: {max(1, int((end - start) / 0.22))}, '
            f'yoyo: true, ease: "sine.inOut"}}, {round(start, 2)});']
