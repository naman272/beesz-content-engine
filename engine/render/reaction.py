"""Reaction Reel: reaction clip + hook -> text scenes over zooming backgrounds -> CTA card, with music."""
import random
import subprocess
from pathlib import Path

from engine import assets
from engine.render import overlays, site

FPS = 30


def durations(post: dict, clip_seconds: float) -> list[float]:
    hook = min(clip_seconds, max(2.8, min(3.6, 1.6 + 0.04 * len(post["hook"]))))
    points = [min(4.0, 2.0 + 0.045 * len(p["text"])) for p in post["points"]]
    return [hook, *points, 2.6]


def render(post: dict, account: dict, clip: dict, backgrounds: list[dict], music: Path, out: Path,
           site_clip: Path | None = None, link: str | None = None) -> Path:
    """backgrounds: one picked background entry per point. site_clip/link: for promos, a screen capture of the
    site shown before the closing card, which points to the link in bio."""
    work = out.parent / "layers"
    total_points = len(post["points"])
    layers = [(overlays.hook_layer(post["hook"]), True)]
    layers += [(overlays.scene_layer(p["text"], i, total_points, account["handle"]), True)
               for i, p in enumerate(post["points"], 1)]
    layers.append((overlays.cta_layer(post["cta"], account["handle"], link), False))
    pngs = overlays.render(layers, account, work)

    secs = durations(post, clip["seconds"])
    site_secs = site.SECONDS if site_clip else 0.0
    total = sum(secs) + site_secs
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-t", f"{secs[0]:.2f}", "-i", str(assets.reaction_path(clip)),
           "-loop", "1", "-t", f"{secs[0]:.2f}", "-framerate", str(FPS), "-i", str(pngs[0])]
    for bg, png, d in zip(backgrounds, pngs[1:-1], secs[1:-1]):
        cmd += ["-i", str(assets.path(bg["file_v"])),
                "-loop", "1", "-t", f"{d:.2f}", "-framerate", str(FPS), "-i", str(png)]
    cmd += ["-loop", "1", "-t", f"{secs[-1]:.2f}", "-framerate", str(FPS), "-i", str(pngs[-1])]
    music_input = 2 + 2 * total_points + 1
    music_start = random.uniform(0, max(0.0, 58 - total))
    cmd += ["-ss", f"{music_start:.2f}", "-i", str(music)]
    if site_clip:
        cmd += ["-i", str(site_clip)]

    norm = "fps=30,format=yuv420p,setsar=1"
    f = [f"[0:v]scale=1080:1920,{norm}[r]", f"[r][1:v]overlay=0:0:shortest=1,{norm}[s0]"]
    for k in range(total_points):
        bg_in, txt_in = 2 + 2 * k, 3 + 2 * k
        frames = round(secs[k + 1] * FPS)
        f.append(
            f"[{bg_in}:v]scale=1188:2112,zoompan=z='min(zoom+0.0009,1.12)':x='iw/2-(iw/zoom/2)'"
            f":y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={FPS},{norm}[b{k}]"
        )
        f.append(f"[b{k}][{txt_in}:v]overlay=0:0:shortest=1,{norm}[s{k + 1}]")
    cta_in = 2 + 2 * total_points
    scenes = [f"[s{i}]" for i in range(total_points + 1)]
    if site_clip:
        f.append(f"[{music_input + 1}:v]scale=1080:1920,{norm}[site]")
        scenes.append("[site]")
    f.append(f"[{cta_in}:v]scale=1080:1920,{norm}[cta]")
    scenes.append("[cta]")
    f.append("".join(scenes) + f"concat=n={len(scenes)}:v=1:a=0[v]")
    f.append(f"[{music_input}:a]atrim=0:{total:.2f},afade=t=in:d=0.3,afade=t=out:st={total - 1.2:.2f}:d=1.2[a]")

    cmd += ["-filter_complex", ";".join(f), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    return out
