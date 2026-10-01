import base64

import numpy as np

from oi.speech import FakeTranscriber, decode_pcm, resample

RATE = 16000


def pcm_b64(samples: np.ndarray) -> str:
    return base64.b64encode((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()).decode()


def test_browser_audio_becomes_float_samples():
    tone = np.sin(np.linspace(0, 2 * np.pi * 440, RATE)).astype(np.float32) * 0.5
    samples = decode_pcm(pcm_b64(tone), RATE)
    assert samples.dtype == np.float32 and len(samples) == RATE
    assert np.max(np.abs(samples - tone)) < 1e-3


def test_other_sample_rates_are_brought_to_16_khz():
    one_second_48k = np.zeros(48000, np.float32)
    assert len(resample(one_second_48k, 48000)) == RATE
    assert len(decode_pcm(pcm_b64(one_second_48k), 48000)) == RATE


def test_broken_audio_is_empty():
    assert len(decode_pcm("not base64 !!", RATE)) == 0
    assert len(decode_pcm(base64.b64encode(b"\x01").decode(), RATE)) == 0  # half a sample


async def test_fake_transcriber_answers_from_its_script():
    fake = FakeTranscriber("Wie schwer ist das?")
    assert await fake.transcribe(np.zeros(RATE, np.float32), "de") == "Wie schwer ist das?"
    assert fake.calls == 1
