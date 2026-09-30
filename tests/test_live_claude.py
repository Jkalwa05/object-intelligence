"""A real Claude call (about 2 cents). Runs only with `uv run pytest -m claude`."""

import cv2
import pytest
from ultralytics.utils import ASSETS

from oi.config import Settings
from oi.contracts import Observation
from oi.identify import ClaudeIdentifier, IdentifyRequest
from oi.views import encode_for_claude


@pytest.mark.claude
async def test_real_call_returns_valid_observation():
    image = cv2.imread(str(ASSETS / "bus.jpg"))
    jpeg = encode_for_claude(image[200:900, :], long_edge=1024, quality=90)
    result = await ClaudeIdentifier(Settings.from_env()).identify(
        IdentifyRequest(jpeg=jpeg, coarse_label="bus", history="none", pending_view=None, language="de"))
    assert isinstance(result.observation, Observation)
    assert result.cost_usd > 0 and result.latency_s > 0
    print(f"\n{result.model}: {result.observation.model_dump_json()}\n"
          f"tokens {result.input_tokens}/{result.output_tokens}, ${result.cost_usd:.4f}, {result.latency_s:.1f} s")
