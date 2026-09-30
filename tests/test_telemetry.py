import json
from datetime import datetime

import pytest

from oi.config import Settings
from oi.telemetry import CallLog, CallRecord, Telemetry


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_telemetry_snapshot():
    clock = FakeClock()
    tel = Telemetry(Settings(), mode="hybrid", model_label="claude-opus-5-5", clock=clock)
    for i in range(20):
        clock.now = i * 0.1
        tel.frame_processed(10.0)
    tel.call_started()
    tel.call_started()
    tel.call_finished(2.5, 0.02)
    tel.call_finished(3.0, 0.03)
    tel.set_sharpness(120.0)
    snap = tel.snapshot(frames_dropped=4)
    assert snap.fps_processed == pytest.approx(10.0) and snap.det_ms == 10.0
    assert (snap.calls_session, snap.id_ms_last, snap.frames_dropped) == (2, 3000.0, 4)
    assert snap.cost_session_usd == pytest.approx(0.05)
    assert (snap.sharpness_focus, snap.model, snap.mode, snap.language) == (120.0, "claude-opus-5-5", "hybrid", "de")


def test_snapshot_without_frames_is_zero():
    snap = Telemetry(Settings(), mode="lokal", model_label="–", clock=FakeClock()).snapshot(frames_dropped=0)
    assert (snap.fps_processed, snap.det_ms, snap.id_ms_last, snap.calls_session) == (0.0, 0.0, None, 0)


def _record(n: int = 1) -> CallRecord:
    return CallRecord(n=n, track_id=5, jpeg=b"\xff\xd8jpeg", request_text="Coarse detector label: cup",
                      observation={"category": "cup"}, error=None, input_tokens=2000, output_tokens=500,
                      cost_usd=0.018, latency_s=2.4, model="claude-opus-5-5", level_after="likely")


def test_call_log_writes_files(tmp_path):
    log = CallLog(tmp_path, enabled=True, now=lambda: datetime(2026, 9, 30, 15, 30, 0))
    log.write(_record())
    (session,) = list(tmp_path.iterdir())
    assert session.name == "2026-09-30_15-30-00"
    assert (session / "001_track5.jpg").read_bytes() == b"\xff\xd8jpeg"
    data = json.loads((session / "001_track5.json").read_text())
    assert data["level_after"] == "likely" and data["cost_usd"] == 0.018 and "jpeg" not in data


def test_call_log_disabled(tmp_path):
    CallLog(tmp_path, enabled=False).write(_record())
    assert list(tmp_path.iterdir()) == []
