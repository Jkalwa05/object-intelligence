import json
import struct
from pathlib import Path

import cv2
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from oi.config import Settings
from oi.identify import FakeIdentifier
from oi.perception import FakeDetector
from oi.server import create_app
from tests.helpers import sharp_image, trk

BOX = (400, 200, 700, 500)
CUP, BOOK = trk(1, BOX), trk(2, (1000, 100, 1200, 300), label="book")
HAND = trk(99, (450, 400, 650, 520), label="hand")  # the cup is held: only held objects get focus


def frame_message(image=None, frame_id: int = 1, t_ms: float = 0.0) -> bytes:
    image = sharp_image(boxes=(BOX,)) if image is None else image
    ok, jpeg = cv2.imencode(".jpg", image)
    h, w = image.shape[:2]
    header = json.dumps({"frame_id": frame_id, "t_capture_ms": t_ms, "w": w, "h": h}).encode()
    return struct.pack(">I", len(header)) + header + jpeg.tobytes()


def app_with(identifier_result, detector=None, static_dir: Path = Path("/nonexistent"), settings=None):
    detector = detector or FakeDetector([[CUP, HAND]])

    async def factory():
        return identifier_result

    return create_app(settings or Settings(log_calls=False), detector, factory, static_dir), detector


def next_of(ws, kind):
    """The next message of one type; the scene calibration message comes first on every connection."""
    while (message := ws.receive_json())["type"] != kind:
        pass
    return message


def drive(ws, image, n):
    """Send n frames 0.1 s apart, each only after the previous one was processed; return every message seen."""
    seen = []
    for i in range(n):
        ws.send_bytes(frame_message(image, frame_id=i + 1, t_ms=i * 100.0))
        while (message := ws.receive_json())["type"] != "tracks":
            seen.append(message)
        seen.append(message)
    return seen


def wait_for_identity(ws, seen, statuses, limit=30):
    while not any(m["type"] == "identity" and m["status"] in statuses for m in seen) and limit:
        seen.append(ws.receive_json())
        limit -= 1
    return [m["status"] for m in seen if m["type"] == "identity"]


def test_ws_frame_produces_tracks_with_seq():
    app, _ = app_with((FakeIdentifier(), None, "hybrid"))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_bytes(frame_message())
        scene = ws.receive_json()
        assert (scene["type"], scene["seq"], scene["calibrating"]) == ("scene", 1, True)
        message = ws.receive_json()
        assert (message["type"], message["seq"], message["focus_id"]) == ("tracks", 2, CUP.id)
        assert message["ts"] > 0


def test_startup_notice_in_local_mode():
    app, _ = app_with((None, "Kein API-Key: nur lokale Erkennung.", "lokal"))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        message = ws.receive_json()
        assert (message["type"], message["text"], message["level"]) == \
            ("notice", "Kein API-Key: nur lokale Erkennung.", "warn")


def test_malformed_messages_are_ignored():
    app, _ = app_with((None, None, "lokal"))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_bytes(b"\x00")
        ws.send_text('{"type":"nope"}')
        ws.send_text("kaputt")
        ws.send_bytes(frame_message())
        assert next_of(ws, "tracks")["type"] == "tracks"


def test_focus_message_pins_track():
    app, _ = app_with((None, None, "lokal"), FakeDetector([[CUP, BOOK]]))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "focus", "track_id": BOOK.id}))
        ws.send_bytes(frame_message(sharp_image(boxes=(BOX, (1000, 100, 1200, 300)))))
        assert next_of(ws, "tracks")["focus_id"] == BOOK.id


def test_second_connection_replaces_first():
    app, detector = app_with((None, None, "lokal"))
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as first:
            with client.websocket_connect("/ws") as second:
                with pytest.raises(WebSocketDisconnect) as closed:
                    first.receive_json()
                assert closed.value.code == 4000
                second.send_bytes(frame_message())
                assert next_of(second, "tracks")["type"] == "tracks"
    assert detector.reset_calls == 2


def test_root_without_build_shows_hint(tmp_path):
    app, _ = app_with((None, None, "lokal"), static_dir=tmp_path / "missing")
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200 and "npm --prefix web run build" in response.text


def test_root_serves_built_frontend(tmp_path):
    (tmp_path / "index.html").write_text("<div id=\"root\"></div>")
    app, _ = app_with((None, None, "lokal"), static_dir=tmp_path)
    with TestClient(app) as client:
        assert 'id="root"' in client.get("/").text


def test_session_budget_survives_reconnect():
    from tests.helpers import cand, obs
    app, _ = app_with((FakeIdentifier(script=[obs(cand("Apple", "iPhone 14"))]), None, "hybrid"),
                      settings=Settings(log_calls=False, max_calls_session=1))
    image = sharp_image(boxes=(BOX,))
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            assert "ready" in wait_for_identity(ws, drive(ws, image, 13), {"ready"})
        with client.websocket_connect("/ws") as ws:
            statuses = wait_for_identity(ws, drive(ws, image, 13), {"paused", "analysing"})
    assert "paused" in statuses and "analysing" not in statuses


def test_foreign_origin_is_rejected():
    app, _ = app_with((None, None, "lokal"))
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
                ws.receive_json()
        assert closed.value.code == 1008
        with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:8766"}) as ws:
            ws.send_bytes(frame_message())
            assert next_of(ws, "tracks")["type"] == "tracks"


def test_profile_reaches_the_browser_and_is_shared_between_connections():
    from oi.contracts import ProductProfile, ProfileFact
    from tests.helpers import cand, obs
    profile = ProductProfile(known=True, summary="Ein Smartphone.", facts=[ProfileFact(label="Chip", value="A15")],
                             released=None, launch_price=None, trivia=[])
    identifier = FakeIdentifier(script=[obs(cand("Apple", "iPhone 14"), cand("Apple", "iPhone 13"))], profile=profile)
    app, _ = app_with((identifier, None, "hybrid"))
    image = sharp_image(boxes=(BOX,))
    ready = []
    with TestClient(app) as client:
        for _ in range(2):  # the second connection gets the profile from the shared store
            with client.websocket_connect("/ws") as ws:
                seen, limit = drive(ws, image, 13), 40
                while not any(m["type"] == "profile" and m["status"] == "ready" for m in seen) and limit:
                    seen.append(ws.receive_json())
                    limit -= 1
                ready += [m for m in seen if m["type"] == "profile" and m["status"] == "ready"]
    assert [m["product"] for m in ready] == ["Apple iPhone 14", "Apple iPhone 14"]
    assert len(identifier.product_requests) == 1


# --- sub-project 6: the precision model -----------------------------------------------------------------------------

def _stored_model():
    from oi.contracts import MeasureSheet, ModelManifest, ModelPart
    from oi.modelstore import ModelStore
    store = ModelStore(None)
    manifest = ModelManifest(model="Apple iPhone 14", slug="apple-iphone-14", size_mm=(71.5, 146.7, 7.8),
                             sheet=MeasureSheet.estimated(), drawing_pages=[], notes="", verdict="good", rounds=1,
                             cost_usd=0.9, created="2026-10-01T22:00:00",
                             parts=[ModelPart(name="Gehäuse", color="#9fc4e8", file="part-01.stl", min_mm=(0, 0, 0),
                                              max_mm=(1, 1, 1), triangles=12)])
    store.put(manifest, [b"solid-bytes"], "cube(1);")
    return store


def test_model_files_are_served_and_nothing_else():
    async def factory():
        return None, None, "lokal"

    app = create_app(Settings(log_calls=False), FakeDetector([]), factory, Path("/nonexistent"), models=_stored_model())
    with TestClient(app) as client:
        part = client.get("/models/apple-iphone-14/part-01.stl")
        assert part.status_code == 200 and part.content == b"solid-bytes"
        assert part.headers["content-type"].startswith("model/stl")
        source = client.get("/models/apple-iphone-14/model.scad")
        assert source.status_code == 200 and source.text == "cube(1);"
        for path in ("/models/apple-iphone-14/manifest.json", "/models/apple-iphone-14/part-99.stl",
                     "/models/unknown/part-01.stl", "/models/apple-iphone-14/..%2Fmanifest.json",
                     "/models/APPLE/part-01.stl"):
            assert client.get(path).status_code == 404, path


def test_no_builder_in_fake_mode_but_one_with_claude_and_a_compiler():
    from oi.identify import ClaudeIdentifier
    from oi.scad import FakeCompiler
    app, _ = app_with((FakeIdentifier(), None, "hybrid"))
    with TestClient(app):
        assert app.state.builder is None

    async def factory():
        return ClaudeIdentifier(Settings(), client=object()), None, "hybrid"

    app = create_app(Settings(log_calls=False), FakeDetector([]), factory, Path("/nonexistent"),
                     compiler=FakeCompiler())
    with TestClient(app):
        assert app.state.builder is not None
    no_compiler = create_app(Settings(log_calls=False), FakeDetector([]), factory, Path("/nonexistent"),
                             model_notice="3D-Modelle aus: Node.js fehlt")
    with TestClient(no_compiler) as client, client.websocket_connect("/ws") as ws:
        assert no_compiler.state.builder is None
        assert next_of(ws, "notice")["text"] == "3D-Modelle aus: Node.js fehlt"
