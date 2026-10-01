"""The evidence book: turns Claude's observations of one object into a ranking and an honest level (spec §2.6).

Pure logic. Every observation is a vote: rank 1 counts 1.0, rank 2 0.5, rank 3 0.25, rank 4 0.125, weighted by crop
quality. Only independent views (different view ids) or a readable model name can make a result certain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from oi import lines
from oi.config import Lang
from oi.contracts import BeliefState, Candidate, Depth, Level, NextView, Observation, RankedCandidate

RANK_WEIGHTS = (1.0, 0.5, 0.25, 0.125)
EPS = 1e-9
CERTAIN_SHARE, CERTAIN_LEAD, CLOSE_LEAD = 0.6, 0.3, 0.15
MAX_EVIDENCE, MAX_RANKED = 6, 3
_CATEGORY_ONLY = Candidate(brand=None, model_name=None, variant=None, depth=Depth.CATEGORY, evidence=[])


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _key(c: Candidate, category: str) -> str:
    key = _normalize(f"{c.brand or ''} {c.model_name or ''}")
    return key or f"category:{_normalize(category)}"


@dataclass
class _Entry:
    key: str
    order: int
    points: float = 0.0
    top_views: set[int] = field(default_factory=set)
    evidence: list[str] = field(default_factory=list)
    sightings: list[tuple[Candidate, Observation]] = field(default_factory=list)


@dataclass
class _Verdict:
    level: Level | None
    final: bool
    ranking: list[_Entry]
    total: float
    indistinct: bool


class Belief:
    def __init__(self, language: Lang) -> None:
        self._lang = language
        self._seen: list[tuple[Observation, int, float]] = []  # observation, view id, quality

    @property
    def observations(self) -> list[Observation]:
        return [o for o, _, _ in self._seen]

    @property
    def is_final(self) -> bool:
        return self._verdict().final

    def add(self, obs: Observation, view_id: int, q: float) -> None:
        self._seen.append((obs, view_id, q))

    def product(self) -> tuple[str, str] | None:
        """(display name, category) of a product worth a profile (sub-project 2): likely or certain, and named
        down to the model; a brand alone or a mere category is no product to describe."""
        v = self._verdict()
        if v.level not in (Level.LIKELY, Level.CERTAIN) or not v.ranking:
            return None
        top = v.ranking[0]
        candidate, observation = top.sightings[-1]
        if candidate.depth not in (Depth.MODEL, Depth.VARIANT):
            return None
        return self._name(top), observation.category

    def snapshot(self, calls_used: int) -> BeliefState:
        v = self._verdict()
        if v.level is None:
            return BeliefState.empty("").model_copy(update={"calls_used": calls_used})
        latest = self._seen[-1][0]
        names = [self._name(e) for e in v.ranking]
        ranked = [RankedCandidate(name=n, share=e.points / v.total) for n, e in zip(names, v.ranking)][:MAX_RANKED]
        top = v.ranking[0] if v.ranking else None
        view_request: NextView | None = None
        if v.level == Level.CATEGORY_ONLY:
            description = latest.generic_description or latest.category
            display = lines.display_name(_CATEGORY_ONLY, latest.category, description, self._lang)
            line = lines.line_category(description, self._lang)
        else:
            display = names[0]
            if v.level == Level.CERTAIN:
                line = lines.line_certain(display, self._lang)
            elif v.level == Level.LIKELY:
                line = lines.line_likely(display, self._lang)
            else:
                second = names[1] if len(names) > 1 else None
                if not v.final and latest.next_view is not None:
                    view_request = latest.next_view
                line = lines.line_unsure(display, second, view_request.view if view_request else None,
                                         not v.indistinct, self._lang)
        return BeliefState(level=v.level, display_name=display, candidates=ranked,
                           evidence=top.evidence[:MAX_EVIDENCE] if top else [], view_request=view_request,
                           final=v.final, calls_used=calls_used, line=line)

    def _verdict(self) -> _Verdict:
        if not self._seen:
            return _Verdict(None, False, [], 0.0, False)
        ranking = self._ranking()
        total = sum(e.points for e in ranking) or 1.0
        latest = self._seen[-1][0]
        top = ranking[0] if ranking else None
        if top is None or top.sightings[-1][0].depth == Depth.CATEGORY:
            category_views = {view for obs, view, _ in self._seen
                              if not obs.candidates or obs.candidates[0].depth == Depth.CATEGORY}
            return _Verdict(Level.CATEGORY_ONLY, len(category_views) >= 2, ranking, total, False)
        share = top.points / total
        lead = share - (ranking[1].points / total if len(ranking) > 1 else 0.0)
        # Ruling (ledger, Task 5): when Claude says the leading candidates look alike from the outside, agreement
        # across views is not independent evidence, so this is checked before the two-view rule.
        indistinct = not latest.distinguishable and len(ranking) > 1
        if self._decisive(top):
            return _Verdict(Level.CERTAIN, True, ranking, total, False)
        if indistinct and latest.next_view is not None:  # another view can still separate them: keep asking for it
            return _Verdict(Level.UNSURE, False, ranking, total, False)
        if indistinct:
            return _Verdict(Level.UNSURE, True, ranking, total, True)
        # Ruling (ledger, final review): Claude's own "low" blocks the two-view rule as well; a slightly tilted
        # re-grip can count as a new view, so agreement alone must not make look-alikes certain.
        if latest.self_assessment == "low":
            return _Verdict(Level.UNSURE, False, ranking, total, False)
        if len(top.top_views) >= 2 and share >= CERTAIN_SHARE - EPS and lead >= CERTAIN_LEAD - EPS:
            return _Verdict(Level.CERTAIN, True, ranking, total, False)
        if lead < CLOSE_LEAD - EPS or latest.self_assessment == "low":
            return _Verdict(Level.UNSURE, False, ranking, total, False)
        return _Verdict(Level.LIKELY, False, ranking, total, False)

    def _ranking(self) -> list[_Entry]:
        entries: dict[str, _Entry] = {}
        for obs, view_id, q in self._seen:
            for rank, c in enumerate(obs.candidates[:len(RANK_WEIGHTS)]):
                key = _key(c, obs.category)
                entry = entries.setdefault(key, _Entry(key=key, order=len(entries)))
                entry.points += RANK_WEIGHTS[rank] * q
                entry.sightings.append((c, obs))
                if rank == 0:
                    entry.top_views.add(view_id)
                entry.evidence.extend(e for e in c.evidence if e not in entry.evidence)
        return sorted(entries.values(), key=lambda e: (-e.points, e.order))

    @staticmethod
    def _decisive(entry: _Entry) -> bool:
        """The candidate's model name is readable on the object, as whole words, in one of its own observations.
        Short names without a digit ("Pro", "One") are too common to prove anything."""
        for c, obs in entry.sightings:
            name = _normalize(c.model_name or "")
            if len(name) < 4 and not any(ch.isdigit() for ch in name):
                continue
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", _normalize(" ".join(obs.readable_text))):
                return True
        return False

    def _name(self, entry: _Entry) -> str:
        c, obs = entry.sightings[-1]
        last_two = [s for s, _ in entry.sightings[-2:]]
        confirmed = len(last_two) == 2 and last_two[0].variant and last_two[0].variant == last_two[1].variant
        if c.depth == Depth.VARIANT and not confirmed:
            c = c.model_copy(update={"depth": Depth.MODEL})
        return lines.display_name(c, obs.category, obs.generic_description, self._lang)
