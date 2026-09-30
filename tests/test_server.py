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


def frame_message(image=None, frame_id: int = 1, t_ms: float = 0.0) -> bytes:
    image = sharp_image(boxes=(BOX,)) if image is None else image
    ok, jpeg = cv2.imencode(".jpg", image)
    h, w = image.shape[:2]
    header = json.dumps({"frame_id": frame_id, "t_capture_ms": t_ms, "w": w, "h": h}).encode()
    return struct.pack(">I", len(header)) + header + jpeg.tobytes()


def app_with(identifier_result, detector=None, static_dir: Path = Path("/nonexistent")):
    detector = detector or FakeDetector([[CUP]])

    async def factory():
        return identifier_result

    return create_app(Settings(log_calls=False), detector, factory, static_dir), detector


def test_ws_frame_produces_tracks_with_seq():
    app, _ = app_with((FakeIdentifier(), None, "hybrid"))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_bytes(frame_message())
        message = ws.receive_json()
        assert (message["type"], message["seq"], message["focus_id"]) == ("tracks", 1, CUP.id)
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
        assert ws.receive_json()["type"] == "tracks"


def test_focus_message_pins_track():
    app, _ = app_with((None, None, "lokal"), FakeDetector([[CUP, BOOK]]))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "focus", "track_id": BOOK.id}))
        ws.send_bytes(frame_message(sharp_image(boxes=(BOX, (1000, 100, 1200, 300)))))
        assert ws.receive_json()["focus_id"] == BOOK.id


def test_second_connection_replaces_first():
    app, detector = app_with((None, None, "lokal"))
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as first:
            with client.websocket_connect("/ws") as second:
                with pytest.raises(WebSocketDisconnect) as closed:
                    first.receive_json()
                assert closed.value.code == 4000
                second.send_bytes(frame_message())
                assert second.receive_json()["type"] == "tracks"
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
