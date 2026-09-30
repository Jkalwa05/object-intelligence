"""Focus selector: which tracked object gets the expensive identification (spec §2.3). Pure logic."""

from __future__ import annotations

import math

from oi.config import Settings
from oi.contracts import Track
from oi.privacy import privacy_veto

EPS = 1e-6  # tolerance for time comparisons
SIZE_FULL = 0.15  # an object covering 15 % of the frame gets the full size factor
STILL_LIMIT = 0.5  # frame diagonals per second at which the steady factor reaches 0
NEW_FULL_S, NEW_ZERO_S = 2.0, 6.0
EMA_ALPHA = 0.5
HELD_MEMORY_S = 2.0  # a hand that was seen on the object within 2 s still counts (hand detection flickers)


def split_tracks(tracks: list[Track], s: Settings) -> tuple[list[Track], list[Track]]:
    """(visible, hands): visible drops people and body parts; hands only give the focus bonus."""
    excluded = {label.lower() for label in s.excluded_labels}
    hand_labels = {label.lower() for label in s.hand_labels}
    visible = [t for t in tracks if t.label.lower() not in excluded]
    hands = [t for t in tracks if t.label.lower() in hand_labels]
    return visible, hands


def _area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


class FocusSelector:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._focus: int | None = None
        self._pinned: int | None = None
        self._challenger: int | None = None
        self._challenge_since = 0.0
        self._last: dict[int, tuple[float, float, float]] = {}  # id -> (cx, cy, t)
        self._velocity: dict[int, float] = {}  # smoothed, in frame diagonals per second
        self._steady: dict[int, float] = {}
        self._last_held: dict[int, float] = {}

    def pin(self, track_id: int | None) -> None:
        """Make this track the focus until it disappears; None returns to automatic choice."""
        self._pinned = track_id

    def steady(self, track_id: int) -> float:
        return self._steady.get(track_id, 0.0)

    def held(self, track_id: int, now: float) -> bool:
        """A hand was on this object within the last 2 s."""
        return now - self._last_held.get(track_id, float("-inf")) <= HELD_MEMORY_S

    def update(self, visible: list[Track], hands: list[Track], frame_w: int, frame_h: int, now: float,
               people: list[Track] = ()) -> int | None:
        """`people`: raw person and face detections, so regions on a person's body or face never get focus.

        Only held objects become the focus automatically (the product is "hold something up"); a focus keeps its
        place while it stays in view. Everything else can be chosen with a click (`pin`)."""
        diag = math.hypot(frame_w, frame_h)
        ids = {t.id for t in visible}
        for t in visible:
            self._track_motion(t, diag, now)
            if self._touches_hand(t, hands):
                self._last_held[t.id] = now
        for gone in set(self._last) - ids:
            del self._last[gone], self._velocity[gone], self._steady[gone]
            self._last_held.pop(gone, None)

        if self._pinned is not None:
            if self._pinned in ids:
                self._focus = self._pinned
                self._challenger = None
                return self._focus
            self._pinned = None

        frame_area = frame_w * frame_h
        scores = {t.id: self._score(t, hands, frame_w, frame_h, diag, now) for t in visible
                  if self._eligible(t, frame_area)
                  and (t.id == self._focus or self.held(t.id, now))
                  and (self.held(t.id, now) or not privacy_veto(t, list(people), self._s))}
        if not scores:
            self._focus, self._challenger = None, None
            return None
        best = max(scores, key=scores.__getitem__)
        if self._focus not in scores:
            self._focus, self._challenger = best, None
        elif best != self._focus and scores[best] - scores[self._focus] >= self._s.focus_switch_margin - EPS:
            if self._challenger != best:
                self._challenger, self._challenge_since = best, now
            elif now - self._challenge_since >= self._s.focus_switch_hold_s - EPS:
                self._focus, self._challenger = best, None
        else:
            self._challenger = None
        return self._focus

    def _eligible(self, t: Track, frame_area: float) -> bool:
        share = _area(t.box) / frame_area
        return self._s.min_area <= share <= self._s.max_area and t.age_frames >= self._s.min_age_frames

    def _score(self, t: Track, hands: list[Track], frame_w: int, frame_h: int, diag: float, now: float) -> float:
        area = _area(t.box)
        size = min(1.0, area / (frame_w * frame_h) / SIZE_FULL)
        cx, cy = _center(t.box)
        center = max(0.0, 1.0 - math.hypot(cx - frame_w / 2, cy - frame_h / 2) / (diag / 2))
        held = self._touches_hand(t, hands)
        age = now - t.first_seen_ts
        new = 1.0 if age < NEW_FULL_S else max(0.0, 1.0 - (age - NEW_FULL_S) / (NEW_ZERO_S - NEW_FULL_S))
        w_size, w_center, w_hand, w_steady, w_new = self._s.focus_weights
        return (w_size * size + w_center * center + w_hand * float(held) + w_steady * self._steady[t.id]
                + w_new * new)

    @staticmethod
    def _touches_hand(t: Track, hands: list[Track]) -> bool:
        area = _area(t.box)
        return any(_overlap(t.box, h.box) > 0.10 * min(area, _area(h.box)) for h in hands)

    def _track_motion(self, t: Track, diag: float, now: float) -> None:
        cx, cy = _center(t.box)
        previous = self._last.get(t.id)
        velocity = self._velocity.get(t.id, 0.0)
        if previous is not None and now > previous[2]:
            px, py, pt = previous
            instant = math.hypot(cx - px, cy - py) / diag / (now - pt)
            velocity = EMA_ALPHA * instant + (1 - EMA_ALPHA) * velocity
        self._velocity[t.id] = velocity
        self._last[t.id] = (cx, cy, now)
        self._steady[t.id] = 1.0 - min(1.0, velocity / STILL_LIMIT)
