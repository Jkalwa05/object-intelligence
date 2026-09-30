"""Live numbers for the HUD's telemetry corner (spec §3) and the call log in runs/ (spec §4)."""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from oi.config import Settings
from oi.contracts import TelemetryMsg

FPS_WINDOW_S = 2.0
DET_MS_SAMPLES = 30


@dataclass
class SessionBudget:
    """Calls and cost of the whole server run, shared by every browser connection, so a reload never resets the cost
    brake (spec §4)."""

    calls: int = 0
    cost_usd: float = 0.0
    cap_notice_sent: bool = False


class Telemetry:
    def __init__(self, settings: Settings, mode: Literal["hybrid", "lokal"], model_label: str,
                 clock: Callable[[], float] = time.monotonic, budget: SessionBudget | None = None) -> None:
        self._settings = settings
        self._mode = mode
        self._model_label = model_label
        self._clock = clock
        self._frame_times: deque[float] = deque()
        self._det_ms: deque[float] = deque(maxlen=DET_MS_SAMPLES)
        self._sharpness: float | None = None
        self.budget = budget if budget is not None else SessionBudget()
        self._failed = 0
        self._id_ms_last: float | None = None

    @property
    def calls_session(self) -> int:
        return self.budget.calls

    def frame_processed(self, det_ms: float) -> None:
        now = self._clock()
        self._frame_times.append(now)
        self._det_ms.append(det_ms)
        self._forget_old_frames(now)

    def set_sharpness(self, value: float | None) -> None:
        self._sharpness = value

    def call_started(self) -> None:
        self.budget.calls += 1

    def call_finished(self, latency_s: float, cost_usd: float) -> None:
        self.budget.cost_usd += cost_usd
        self._id_ms_last = latency_s * 1000.0

    def call_failed(self) -> None:
        self._failed += 1

    def snapshot(self, frames_dropped: int) -> TelemetryMsg:
        self._forget_old_frames(self._clock())
        det_ms = sum(self._det_ms) / len(self._det_ms) if self._det_ms else 0.0
        return TelemetryMsg(
            fps_processed=round(len(self._frame_times) / FPS_WINDOW_S, 1), frames_dropped=frames_dropped,
            det_ms=round(det_ms, 1), id_ms_last=self._id_ms_last,
            sharpness_focus=None if self._sharpness is None else round(self._sharpness, 1),
            calls_session=self.budget.calls, cost_session_usd=round(self.budget.cost_usd, 4), model=self._model_label,
            mode=self._mode, language=self._settings.language)

    def _forget_old_frames(self, now: float) -> None:
        while self._frame_times and now - self._frame_times[0] >= FPS_WINDOW_S:
            self._frame_times.popleft()


@dataclass
class CallRecord:
    n: int
    track_id: int
    jpeg: bytes
    request_text: str
    observation: dict | None
    error: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str
    level_after: str | None


class CallLog:
    """Every Claude call as `<nnn>_track<id>.jpg` (the crop that was sent) plus `.json`, one folder per session."""

    def __init__(self, runs_dir: Path, enabled: bool, now: Callable[[], datetime] = datetime.now) -> None:
        self._runs_dir = runs_dir
        self._enabled = enabled
        self._now = now
        self._session_dir: Path | None = None

    def write(self, record: CallRecord) -> None:
        if not self._enabled:
            return
        if self._session_dir is None:
            self._session_dir = self._runs_dir / self._now().strftime("%Y-%m-%d_%H-%M-%S")
            self._session_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{record.n:03d}_track{record.track_id}"
        (self._session_dir / f"{stem}.jpg").write_bytes(record.jpeg)
        data = asdict(record)
        del data["jpeg"]
        (self._session_dir / f"{stem}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
