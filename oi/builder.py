"""The precision model builder (sub-project 6, spec §3–§10).

One product at a time: research → drawing → CAD → compile → up to two check rounds → store. The builder belongs to
the app, not to a browser connection, so a reload or a closed tab does not stop a model; every connection listens to
it. Each step first checks that the product's budget still has room for it, and every call counts in the shared
session budget and goes to the call log.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

import numpy as np

from oi import download
from oi.cache import normalize
from oi.config import Settings
from oi.contracts import MeasureSheet, ModelManifest, ModelPart, ModelStatus
from oi.drawings import Fetch, Picture, drawing_pictures
from oi.identify import IdentifyError
from oi.mesh import bounds, read_stl, size_hint, union
from oi.modelcalls import (CadProgram, CadRequest, CheckRequest, ModelCalls, ResearchRequest, apply_check,
                           scad_source)
from oi.modelstore import ModelStore, slug
from oi.render import render_views
from oi.scad import MAX_MODEL_TRIANGLES, CompiledPart, Compiler
from oi.telemetry import CallLog, CallRecord, SessionBudget

log = logging.getLogger(__name__)

Listener = Callable[[str, ModelStatus, int, ModelManifest | None], Awaitable[None]]
RESERVE = {"research": 0.45, "cad": 0.45, "check": 0.35}  # dollars a step may need: checked before it starts
BUSY = ("queued", "researching", "drawing", "modeling", "building", "checking")
R = TypeVar("R")


@dataclass
class _Job:
    model: str
    category: str
    jpeg: bytes | None


class ModelBuilder:
    def __init__(self, settings: Settings, calls: ModelCalls, compiler: Compiler, store: ModelStore,
                 budget: SessionBudget, call_log: CallLog | Any | None, fetch: Fetch = download.fetch,
                 render: Callable[..., list[bytes]] = render_views, now: Callable[[], datetime] = datetime.now) -> None:
        self._s = settings
        self._calls = calls
        self._compiler = compiler
        self._store = store
        self._budget = budget
        self._log = call_log
        self._fetch = fetch
        self._render = render
        self._now = now
        self._listeners: list[Listener] = []
        self._states: dict[str, tuple[ModelStatus, int]] = {}
        self._requests: dict[str, _Job] = {}  # the last request per model, for "Neu bauen"
        self._queue: deque[_Job] = deque()
        self._worker: asyncio.Task[None] | None = None
        self._started = 0  # new models of this server run
        self._logged = 0

    # --- what pipelines use -------------------------------------------------------------------------------------

    def listen(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener) if listener in self._listeners else None

    def state(self, model: str) -> tuple[ModelStatus, int, ModelManifest | None] | None:
        """The model's status, round and (when ready) manifest; None if it was never asked for and is not stored."""
        if (current := self._states.get(normalize(model))) is not None and current[0] != "ready":
            return current[0], current[1], None
        manifest = self._store.get(model)
        return ("ready", manifest.rounds, manifest) if manifest is not None else None

    async def request(self, model: str, category: str, jpeg: bytes | None) -> None:
        """Build the model unless it is stored, being built, waiting, failed or over the session's limit."""
        key = normalize(model)
        if self._store.get(model) is not None or key in self._states:
            return
        self._requests[key] = _Job(model, category, jpeg)
        if self._started >= self._s.max_models_session:
            await self._set(model, "limit")
            return
        self._started += 1
        self._queue.append(self._requests[key])
        await self._set(model, "queued")
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._work())

    async def rebuild(self, model: str) -> None:
        """„Neu bauen“: only after a failure, and like any new model it counts against the session's limit."""
        key = normalize(model)
        if self._states.get(key, (None, 0))[0] != "failed" or key not in self._requests:
            return
        job = self._requests[key]
        del self._states[key]
        await self.request(job.model, job.category, job.jpeg)

    async def wait_idle(self) -> None:
        while self._worker is not None and not self._worker.done():
            await asyncio.gather(self._worker, return_exceptions=True)

    async def aclose(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)

    # --- the job ------------------------------------------------------------------------------------------------

    async def _set(self, model: str, status: ModelStatus, round_: int = 0,
                   manifest: ModelManifest | None = None) -> None:
        self._states[normalize(model)] = (status, round_)
        for listener in list(self._listeners):
            try:
                await listener(model, status, round_, manifest)
            except Exception:  # noqa: BLE001 - a broken connection must not stop the model
                log.exception("a model listener failed")

    async def _work(self) -> None:
        while self._queue:
            job = self._queue.popleft()
            try:
                await self._build(job)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - one broken model must not stop the queue
                log.exception("the precision model of %s failed", job.model)
                await self._set(job.model, "failed")

    async def _call(self, label: str, job: _Job, make: Callable[[], Awaitable[R]],
                    observe: Callable[[R], dict[str, Any]]) -> R:
        self._budget.calls += 1
        try:
            result = await make()
        except IdentifyError as error:
            self._write(label, job, None, error.reason, None)
            raise
        self._budget.cost_usd += result.cost_usd  # type: ignore[attr-defined]
        self._write(label, job, observe(result), None, result)
        return result

    def _write(self, label: str, job: _Job, observation: dict[str, Any] | None, error: str | None,
               result: Any) -> None:
        if self._log is None:
            return
        self._logged += 1
        self._log.write(CallRecord(
            n=self._logged, track_id=-2, jpeg=job.jpeg if label != "research" and job.jpeg else b"",
            request_text=f"model {label}: {job.model}", observation=observation, error=error,
            input_tokens=getattr(result, "input_tokens", 0), output_tokens=getattr(result, "output_tokens", 0),
            cost_usd=getattr(result, "cost_usd", 0.0), latency_s=getattr(result, "latency_s", 0.0),
            model=getattr(result, "model", "–"), level_after=None))

    def _affordable(self, spent: float, step: str) -> bool:
        return spent + RESERVE[step] <= self._s.max_model_cost_usd + 1e-9

    async def _build(self, job: _Job) -> None:
        lang, spent, notes = self._s.language, 0.0, ""
        await self._set(job.model, "researching")
        sheet, allowed = MeasureSheet.estimated(), set[str]()
        try:
            researched = await self._call("research", job, lambda: self._calls.research(
                ResearchRequest(job.model, job.category, lang)), lambda r: r.sheet.model_dump(mode="json"))
            sheet, allowed, spent = researched.sheet, researched.allowed_urls, spent + researched.cost_usd
        except IdentifyError:
            pass  # no research: every dimension is Claude's estimate
        pictures: list[Picture] = []
        pages: list[int] = []
        if sheet.drawing is not None:
            await self._set(job.model, "drawing")
            pictures, pages = await drawing_pictures(sheet.drawing, allowed, fetch=self._fetch)
        if not self._affordable(spent, "cad"):
            await self._set(job.model, "failed")
            return
        await self._set(job.model, "modeling")
        try:
            made = await self._call("cad", job, lambda: self._calls.build_cad(CadRequest(
                job.model, job.category, sheet, pictures, job.jpeg, lang)), lambda r: _program(r.program))
        except IdentifyError:
            await self._set(job.model, "failed")
            return
        program, spent = made.program, spent + made.cost_usd
        await self._set(job.model, "building")
        compiled = {c.name: c for c in await self._compiler.compile(program.shared, program.parts)}
        rounds, good = 0, False
        for round_ in range(1, self._s.model_check_rounds + 1):
            if not self._affordable(spent, "check"):
                notes += " Budget erreicht."
                break
            ok = [compiled[p.name] for p in program.parts if compiled[p.name].stl is not None]
            renders = self._render([(read_stl(c.stl), c.color) for c in ok]) if ok else []  # type: ignore[arg-type]
            errors = {name: c.errors for name, c in compiled.items() if c.stl is None}
            hint = size_hint(_size([c for c in ok]), sheet.size_mm) if ok else None
            await self._set(job.model, "checking", round_)
            try:
                checked = await self._call(f"check {round_}", job, lambda: self._calls.check_cad(CheckRequest(
                    job.model, sheet, pictures, job.jpeg, program, renders, errors, hint, round_,
                    self._s.model_check_rounds, lang)), lambda r: _answer(r.answer))
            except IdentifyError:
                break  # the model so far stays
            rounds, spent = round_, spent + checked.cost_usd
            fixed = apply_check(program, checked.answer)
            changed = [p for p in fixed.parts if fixed.shared != program.shared or p.name not in compiled
                       or p.scad != next(q.scad for q in program.parts if q.name == p.name)]
            program = fixed
            compiled = {name: c for name, c in compiled.items() if name in {p.name for p in program.parts}}
            if changed:
                await self._set(job.model, "building")
                compiled.update({c.name: c for c in await self._compiler.compile(program.shared, changed)})
            if checked.answer.verdict == "good":
                good = True
                break
        await self._finish(job, sheet, pages, program, compiled, rounds, good, spent, notes)

    async def _finish(self, job: _Job, sheet: MeasureSheet, pages: list[int], program: CadProgram,
                      compiled: dict[str, CompiledPart], rounds: int, good: bool, spent: float, notes: str) -> None:
        kept: list[tuple[CompiledPart, np.ndarray]] = []
        dropped, total = [], 0
        for part in program.parts:
            result = compiled.get(part.name)
            try:
                triangles = read_stl(result.stl) if result is not None and result.stl is not None else None
            except ValueError:
                triangles = None
            if triangles is None or len(triangles) == 0 or total + len(triangles) > MAX_MODEL_TRIANGLES:
                dropped.append(part.name)
                continue
            total += len(triangles)
            kept.append((result, triangles))  # type: ignore[arg-type]
        if not kept:
            await self._set(job.model, "failed")
            return
        if dropped:
            notes += f" Weggelassen, weil sie nicht gebaut werden konnten: {', '.join(dropped)}."
        parts = []
        for number, (result, triangles) in enumerate(kept, start=1):
            low, high = bounds(triangles)
            parts.append(ModelPart(name=result.name, color=result.color, file=f"part-{number:02d}.stl", min_mm=low,
                                   max_mm=high, triangles=len(triangles)))
        low, high = union([(p.min_mm, p.max_mm) for p in parts])
        measured = (high[0] - low[0], high[1] - low[1], high[2] - low[2])
        manifest = ModelManifest(
            model=job.model, slug=slug(job.model), parts=parts, size_mm=sheet.size_mm or measured, sheet=sheet,
            drawing_pages=pages, notes=" ".join(f"{program.notes} {notes}".split()),
            verdict="good" if good else "fix" if rounds else "unchecked", rounds=rounds, cost_usd=round(spent, 4),
            created=self._now().isoformat(timespec="seconds"))
        final = CadProgram(shared=program.shared, parts=[p for p in program.parts if p.name not in dropped],
                           notes=program.notes)
        self._store.put(manifest, [result.stl for result, _ in kept], scad_source(final))  # type: ignore[misc]
        await self._set(job.model, "ready", rounds, manifest)


def _size(parts: list[CompiledPart]) -> tuple[float, float, float]:
    low, high = union([bounds(read_stl(c.stl)) for c in parts if c.stl is not None])
    return high[0] - low[0], high[1] - low[1], high[2] - low[2]


def _program(program: CadProgram) -> dict[str, Any]:
    return {"shared": program.shared, "notes": program.notes,
            "parts": [{"name": p.name, "color": p.color, "scad": p.scad} for p in program.parts]}


def _answer(answer: Any) -> dict[str, Any]:
    return {"verdict": answer.verdict, "issues": answer.issues, "shared": answer.shared, "remove": answer.remove,
            "parts": [{"name": p.name, "color": p.color, "scad": p.scad} for p in answer.parts]}
