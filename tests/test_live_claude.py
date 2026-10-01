"""Real Claude calls (about 2 cents each). Run only with `uv run pytest -m claude`."""

import cv2
import numpy as np
import pytest
from ultralytics.utils import ASSETS

from oi.config import Settings
from oi.contracts import Observation
from oi.identify import ClaudeIdentifier, IdentifyRequest, ProductRequest, SceneRequest
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


@pytest.mark.claude
async def test_real_scene_call_names_and_places_the_objects():
    image = np.full((720, 1280, 3), 235, np.uint8)
    cv2.circle(image, (320, 216), 70, (40, 40, 220), -1)  # a red ball, centre at (0.25, 0.3)
    cv2.rectangle(image, (770, 360), (1150, 650), (200, 120, 30), -1)  # a blue box, centre at (0.75, 0.7)
    jpeg = cv2.imencode(".jpg", image)[1].tobytes()
    result = await ClaudeIdentifier(Settings.from_env()).describe_scene(SceneRequest(jpeg=jpeg, language="de"))
    centres = [((i.box[0] + i.box[2]) / 2, (i.box[1] + i.box[3]) / 2) for i in result.items]
    assert any(abs(x - 0.25) < 0.1 and abs(y - 0.3) < 0.1 for x, y in centres)
    assert any(abs(x - 0.75) < 0.1 and abs(y - 0.7) < 0.1 for x, y in centres)
    assert result.cost_usd > 0
    print(f"\n{result.model}: {[(i.label, i.box) for i in result.items]}\n"
          f"tokens {result.input_tokens}/{result.output_tokens}, ${result.cost_usd:.4f}, {result.latency_s:.1f} s")


@pytest.mark.claude
async def test_real_profile_knows_the_iphone_14():
    result = await ClaudeIdentifier(Settings.from_env()).describe_product(
        ProductRequest(product="Apple iPhone 14", category="Smartphone", language="de"))
    assert result.profile.known and result.profile.summary and len(result.profile.facts) >= 4
    print(f"\n{result.model}: {result.profile.model_dump_json()}\n"
          f"tokens {result.input_tokens}/{result.output_tokens}, ${result.cost_usd:.4f}, {result.latency_s:.1f} s")


@pytest.mark.claude
async def test_real_research_finds_the_iphone_14_size():
    from oi.modelcalls import ClaudeModelCalls, ResearchRequest
    settings = Settings.from_env()
    result = await ClaudeModelCalls(ClaudeIdentifier(settings), settings).research(
        ResearchRequest(model="Apple iPhone 14", category="Smartphone", language="de"))
    sheet = result.sheet
    assert sheet.size_mm is not None and sheet.sources
    assert all(abs(a - b) <= 1.0 for a, b in zip(sheet.size_mm, (71.5, 146.7, 7.8), strict=True))
    print(f"\n{sheet.model_dump_json(indent=1)}\nallowed {sorted(result.allowed_urls)}\n"
          f"searches {result.searches}, tokens {result.input_tokens}/{result.output_tokens}, ${result.cost_usd:.3f}, "
          f"{result.latency_s:.0f} s")
