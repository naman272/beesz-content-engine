"""Free voiceover with Kokoro (open-source TTS, Apache 2.0) on CPU via kokoro-onnx.

Model files are downloaded into models/ (not committed): see MODEL_URLS. CI caches them.
"""
from functools import cache
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
from kokoro_onnx import SAMPLE_RATE, Kokoro

from engine.config import ROOT

MODELS = ROOT / "models"
MODEL_URLS = {
    "kokoro-v1.0.int8.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.int8.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
}
# One voice per account so each page sounds like its own person
VOICES = {"acc1": "am_michael", "acc2": "af_heart", "acc3": "am_eric", "acc4": "am_puck", "acc5": "af_nicole"}
SPEED = 1.2


class _Kokoro(Kokoro):
    """kokoro-onnx 0.4.7 sends `speed` as int32 to newer model exports, which expect float32."""

    def _create_audio(self, phonemes, voice, speed):
        tokens = np.array(self.tokenizer.tokenize(phonemes[:510]), dtype=np.int64)
        style = voice[len(tokens)]
        inputs = {"input_ids": [[0, *tokens, 0]], "style": np.array(style, dtype=np.float32),
                  "speed": np.array([speed], dtype=np.float32)}
        return self.sess.run(None, inputs)[0], SAMPLE_RATE


def ensure_models() -> None:
    MODELS.mkdir(exist_ok=True)
    for name, url in MODEL_URLS.items():
        path = MODELS / name
        if not path.exists():
            with requests.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)


@cache
def _engine() -> _Kokoro:
    ensure_models()
    return _Kokoro(str(MODELS / "kokoro-v1.0.int8.onnx"), str(MODELS / "voices-v1.0.bin"))


def say(text: str, account_id: str) -> np.ndarray:
    audio, _ = _engine().create(text, voice=VOICES.get(account_id, "am_michael"), speed=SPEED, lang="en-us")
    return audio


def narrate(lines: list[str], account_id: str, out: Path, gap: float = 0.18) -> list[tuple[float, float]]:
    """Speaks each line in turn into one WAV; returns (start, end) seconds per line for syncing visuals."""
    parts, spans, t = [], [], 0.0
    pause = np.zeros(int(SAMPLE_RATE * gap), dtype=np.float32)
    for line in lines:
        audio = say(line, account_id)
        spans.append((round(t, 3), round(t + len(audio) / SAMPLE_RATE, 3)))
        parts += [audio, pause]
        t += (len(audio) + len(pause)) / SAMPLE_RATE
    sf.write(out, np.concatenate(parts), SAMPLE_RATE)
    return spans
