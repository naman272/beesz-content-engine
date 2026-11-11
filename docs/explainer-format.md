# Explainer Reel format (voiceover + presenter + animated illustrations)

Status: live from 2026-11-04 (owner approved the sample). Free Kokoro voice at 1.2x speed, one voice per
account. 15% of each account's format mix; also allowed for breakdowns, India guides and news.

## Style (from the owner's reference video)
- Vertical 1080x1920, ~30-60 s, narrated throughout.
- Captions follow the voice 2-4 words at a time, top-left, large sans; key words in the accent colour in
  italic serif (e.g. *viral*, *fast*, *five million*).
- One consistent cartoon presenter per account, bottom-right, flat style, gesturing on every beat
  (point, shrug, explain, hand over mouth, thumbs up, celebrate).
- A new UI-style illustration every 2-4 s in the middle of the frame, animated in (pop, stamp, count-up):
  phone stats screen, rubber stamp ("SEALED", "DECODED"), counter ("001"), views chart ("4.9M"),
  chat input box, checklist card, calendar, stacked cards, before/after, progress bar.
- Minimal look: off-white paper background, black + one accent colour, tiny mono meta labels in the
  corners ("// 03 - early", "LAYERS 3/3").

## Build plan
1. Voice: kokoro-onnx (open-source Kokoro-82M, Apache 2.0) on CPU. Synthesize per beat sentence, split
   caption chunk timings within a beat by character length. `engine/voice.py`.
2. Script schema (`format: explainer`): hook + 6-12 beats, each {say, caption_chunks, emphasis,
   visual: {type, params}, gesture}; cta. Opus writes it and picks visuals from the library.
3. Illustration library: one HTML/SVG/GSAP component per visual type, account palette.
   `engine/render/explainer.py`.
4. Presenter: illustrated character, one PNG per pose (`engine/render/presenter.py`). The old vector mascot was removed (owner: never use it).
5. Sample to Telegram for approval; then add `explainer` to `format_mix_next` and KIND_FORMATS.

## v2 upgrade (owner's second reference, target: live in the 15 Nov plan)
Week 1 (to 7 Nov, code only): story-driven scene themes (paper / ink / accent backgrounds per section),
grain texture, camera zoom/pan, wipe + glitch transitions, confetti on wins, word-by-word captions synced
to the voice, typed headline moments with animated underline, ~10 realistic mockups (editor timeline,
terminal, folder, comments, browser, notification stack, app-store card, invoice, calendar invite, bank
statement) layered 2-3 per beat with depth, persistent brand badge. Sample to owner by Friday.
Week 2 (8-14 Nov): detailed illustrated character per account with ~12 poses (owner generates them in
ChatGPT using docs/character-prompts.md), swapped per beat with bounce/squash; polish; live 15 Nov.
