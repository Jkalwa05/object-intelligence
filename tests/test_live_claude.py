"""Real Claude calls (about 2 cents each). Run only with `uv run pytest -m claude`."""

import cv2
import numpy as np
import pytest
from ultralytics.utils import ASSETS

from oi.config import Settings
from oi.contracts import Observation
from oi.identify import ClaudeIdentifier, IdentifyRequest, ProductRequest, SceneRequest, ShapeRequest
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
async def test_real_hologram_of_an_iphone_14_has_its_size():
    image = np.full((700, 400, 3), 128, np.uint8)  # the object-only crop: everything else grey
    cv2.rectangle(image, (50, 50), (350, 650), (228, 198, 169), -1)  # light blue back
    cv2.circle(image, (110, 115), 32, (34, 28, 26), -1)  # two lenses, diagonal
    cv2.circle(image, (170, 175), 32, (34, 28, 26), -1)
    jpeg = cv2.imencode(".jpg", image)[1].tobytes()
    result = await ClaudeIdentifier(Settings.from_env()).describe_shape(
        ShapeRequest(product="Apple iPhone 14", category="Smartphone", jpeg=jpeg, language="de"))
    shape = result.shape
    assert shape.known and len(shape.parts) >= 2 and shape.size_mm is not None
    thin, middle, long = sorted(shape.size_mm)  # whatever the orientation: about 7.8 x 71.5 x 146.7 mm
    assert 5 <= thin <= 12 and 60 <= middle <= 85 and 130 <= long <= 165
    print(f"\n{result.model}: {len(shape.parts)} parts, {shape.size_mm}, "
          f"tokens {result.input_tokens}/{result.output_tokens}, ${result.cost_usd:.4f}, {result.latency_s:.1f} s")
