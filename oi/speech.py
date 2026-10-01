"""Speech to text for questions (sub-project 4): Whisper on the Mac (MLX); the voice never leaves it.

The browser records while the space bar is held and sends 16-bit PCM in base64. Whisper wants 16 kHz floats, which
it gets without ffmpeg: the samples are decoded and, if needed, resampled here.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import threading
from typing import Protocol

import numpy as np

from oi.config import Lang

log = logging.getLogger(__name__)

RATE = 16000
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"  # measured on the M5: 0.4 s for 3.7 s of speech


def resample(samples: np.ndarray, rate: int) -> np.ndarray:
    """Linear resampling to 16 kHz; enough for speech."""
    if rate == RATE or len(samples) == 0:
        return samples.astype(np.float32)
    count = round(len(samples) * RATE / rate)
    positions = np.linspace(0, len(samples) - 1, count)
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)


def decode_pcm(audio_b64: str, rate: int) -> np.ndarray:
    """Base64 little-endian Int16 PCM from the browser as 16 kHz float samples; anything broken is empty."""
    try:
        raw = base64.b64decode(audio_b64, validate=True)
    except (binascii.Error, ValueError):
        return np.zeros(0, np.float32)
    if len(raw) < 2 or rate <= 0:
        return np.zeros(0, np.float32)
    samples = np.frombuffer(raw[: len(raw) // 2 * 2], "<i2").astype(np.float32) / 32768.0
    return resample(samples, rate)


class Transcriber(Protocol):
    async def transcribe(self, samples: np.ndarray, language: Lang) -> str: ...


class WhisperTranscriber:
    """Loads the model on first use (or with `warm_up` at start-up) and runs it in a thread, so the camera keeps
    running while a question is being understood."""

    def __init__(self, model: str = WHISPER_MODEL) -> None:
        self._model = model
        self._lock = threading.Lock()  # one transcription at a time; MLX keeps the model loaded between calls

    def _run(self, samples: np.ndarray, language: Lang) -> str:
        import mlx_whisper  # heavy import: only when speech is actually used

        with self._lock:
            result = mlx_whisper.transcribe(samples, path_or_hf_repo=self._model, language=language)
        return str(result.get("text", "")).strip()

    def warm_up(self) -> None:
        """Download (once) and load the model with a second of silence, in a background thread."""
        def run() -> None:
            try:
                self._run(np.zeros(RATE, np.float32), "de")
            except Exception:  # noqa: BLE001 - questions just start slower then
                log.exception("warming up Whisper failed")
        threading.Thread(target=run, name="whisper-warm-up", daemon=True).start()

    async def transcribe(self, samples: np.ndarray, language: Lang) -> str:
        return await asyncio.to_thread(self._run, samples, language)


class FakeTranscriber:
    """Tests: always hears the same sentence."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def transcribe(self, samples: np.ndarray, language: Lang) -> str:
        self.calls += 1
        return self._text
