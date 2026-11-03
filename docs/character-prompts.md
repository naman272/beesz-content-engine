# Character prompt pack (ChatGPT image generation)

**Start: one shared character for all 5 accounts, 8 poses (8 images).** Per-account characters can come later
(their master prompts are kept below); the renderer uses `assets/characters/<account>/` if it exists, else
`assets/characters/shared/`, and falls back to the current mascot for any missing pose.

## Quick start (about 15 minutes)
1. Open a new ChatGPT chat and paste the **shared master prompt** below. Regenerate until you like him.
2. In the same chat, send the 8 **core pose prompts** one at a time.
3. Save each PNG as `~/code/beesz-content-engine/assets/characters/shared/<pose>.png` (exact names below).
4. Tell Claude "character poses are in".

**Shared master prompt**
> Create a character for an animated explainer series about startups: an Indian man in his late 20s, short
> textured hair, neat short beard, friendly confident expression, black hoodie with a small white logo dot on
> the chest. Waist-up, facing the viewer, arms relaxed, transparent background, no text. Polished 2D cartoon
> illustration with clean outlines and soft cel shading, premium explainer-video style. Portrait 1024x1536.

**Core poses (8):** `neutral`, `point_side`, `explain`, `thinking`, `shocked`, `thumbs_up`, `shrug`, `celebrate`
(prompts in the pose table below). The other 4 (`point_up`, `wink_thumbs`, `facepalm`, `phone`) are optional extras.

---


One character per account, 12 poses each, generated once and reused in every explainer Reel.

## How to do it (about 30-45 minutes total)
1. Open **one new ChatGPT chat per character** (keeping a character in one chat keeps it consistent).
2. Paste the **master prompt** for that account first. Regenerate until you like the character.
3. Then send each **pose prompt** below, one at a time, in the same chat.
4. Download each image as PNG and save it as
   `~/code/beesz-content-engine/assets/characters/<account>/<pose>.png`
   e.g. `assets/characters/acc1/point_up.png`. Use the exact pose names below.
5. Tell Claude "character poses are in". The engine processes and uploads them to the private media repo.

If a background comes out solid instead of transparent, that's fine; the engine removes plain backgrounds.

## Style rules (already inside every master prompt)
Waist-up character, facing the viewer (slight 3/4 is fine), centred, same size and crop in every pose,
**transparent background**, no text, no logos, no props unless the pose asks for one. Polished 2D cartoon
illustration: clean outlines, soft cel shading, warm friendly face, expressive eyebrows and mouth, modern
flat-but-detailed style like a premium explainer video. Portrait image, 1024x1536.

## Later: per-account master prompts (optional)
**acc1 (founder.world1, The Blunt Operator)**
> Create a character for an animated explainer series: an Indian man in his late 20s, short faded haircut,
> light stubble, confident slightly smug half-smile, black hoodie with a small yellow (#FFD60A) logo dot on
> the chest. Waist-up, facing the viewer, arms relaxed, transparent background, no text. Polished 2D cartoon
> illustration with clean outlines and soft cel shading, premium explainer-video style. Portrait 1024x1536.

**acc2 (founder.space1, The Calm Mentor)**
> Create a character for an animated explainer series: an Indian woman in her early 30s, dark wavy hair in a
> loose low bun, small gold earrings, kind calm expression, olive-green cardigan over a cream top.
> Waist-up, facing the viewer, arms relaxed, transparent background, no text. Polished 2D cartoon
> illustration with clean outlines and soft cel shading, premium explainer-video style. Portrait 1024x1536.

**acc3 (founderspace1, The Data Nerd)**
> Create a character for an animated explainer series: an Indian man in his early 30s, neat side-parted
> hair, round black glasses, clean-shaven, curious focused expression, navy sweater over a light-blue
> (#4CC9F0) collared shirt. Waist-up, facing the viewer, arms relaxed, transparent background, no text.
> Polished 2D cartoon illustration with clean outlines and soft cel shading, premium explainer-video style.
> Portrait 1024x1536.

**acc4 (foundr.world, The Hype Builder)**
> Create a character for an animated explainer series: an Indian man in his early 20s, backwards cap,
> short beard, big energetic grin, mint-green (#00F5D4) t-shirt under an open purple (#7B2FF7) overshirt.
> Waist-up, facing the viewer, arms relaxed, transparent background, no text. Polished 2D cartoon
> illustration with clean outlines and soft cel shading, premium explainer-video style. Portrait 1024x1536.

**acc5 (foundr_world, The Storyteller)**
> Create a character for an animated explainer series: an Indian woman in her late 20s, sleek chin-length
> bob, subtle red (#E63946) lipstick, thoughtful knowing smile, black turtleneck with a red blazer.
> Waist-up, facing the viewer, arms relaxed, transparent background, no text. Polished 2D cartoon
> illustration with clean outlines and soft cel shading, premium explainer-video style. Portrait 1024x1536.

## Pose prompts (send each in the same chat, after the master prompt)
Start every pose prompt with: **"Same character, same outfit, same art style, same size and crop,
transparent background, no text. Pose:"** and then add one of these:

| File name | Pose |
|---|---|
| `neutral.png` | standing relaxed, friendly slight smile, arms down |
| `point_up.png` | pointing up with the index finger, confident "listen to this" face |
| `point_side.png` | pointing to the viewer's left with one hand, looking that way, explaining |
| `explain.png` | both hands open in front of the chest, mid-explanation, mouth slightly open |
| `thinking.png` | hand on chin, eyes looking up, thinking |
| `shocked.png` | both hands on cheeks, eyes wide, mouth open in shock |
| `wink_thumbs.png` | winking, one thumb up, cheeky smile |
| `thumbs_up.png` | both thumbs up, big smile |
| `shrug.png` | shrugging with palms up, eyebrows raised, "what can you do" face |
| `celebrate.png` | both fists up celebrating, huge smile, eyes closed with joy |
| `facepalm.png` | one hand covering the face, exasperated |
| `phone.png` | holding a smartphone in one hand, looking at it with raised eyebrows |
