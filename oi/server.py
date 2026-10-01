"""FastAPI app: WebSocket /ws for frames and HUD messages, plus the built frontend (spec §2.7, §4).

One browser connection at a time: a new one (reload, second tab) replaces the old one and starts with fresh tracks.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from oi.config import Settings
from oi.contracts import NoticeMsg, ServerMsg, parse_client_message
from oi.faces import FaceFinder
from oi.hands import HandFinder
from oi.builder import ModelBuilder
from oi.identify import ClaudeIdentifier, Identifier
from oi.ingest import FrameFormatError, FrameSlot, parse_frame_message
from oi.perception import Detector
from oi.modelcalls import ClaudeModelCalls, ModelCalls
from oi.modelstore import ModelStore
from oi.pipeline import Pipeline
from oi.profiles import ProfileStore
from oi.scad import Compiler
from oi.speech import Transcriber
from oi.telemetry import CallLog, SessionBudget, Telemetry

log = logging.getLogger(__name__)

IdentifierFactory = Callable[[], Awaitable[tuple[Identifier | None, str | None, Literal["hybrid", "lokal"]]]]
REPLACED_CODE = 4000
POLICY_VIOLATION = 1008
VITE_DEV_PORT = 5173
TELEMETRY_EVERY_S = 1.0
NOT_BUILT = ('<!doctype html><meta charset="utf-8"><title>Object Intelligence</title>'
             "<p>Frontend nicht gebaut: <code>npm --prefix web install &amp;&amp; npm --prefix web run build</code></p>")


class Sender:
    """Stamps every server message with a running `seq` and the send time, one message at a time."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws
        self._seq = 0
        self._lock = asyncio.Lock()

    async def send(self, message: ServerMsg) -> None:
        async with self._lock:
            self._seq += 1
            stamped = message.model_copy(update={"seq": self._seq, "ts": time.time()})
            with contextlib.suppress(Exception):  # the browser may already be gone; the receive loop notices
                await self._ws.send_text(stamped.model_dump_json())


async def _tick(pipeline: Pipeline, slot: FrameSlot) -> None:
    while True:
        await asyncio.sleep(TELEMETRY_EVERY_S)
        await pipeline.telemetry_tick(slot.dropped)


def default_model_calls(identifier: Identifier | None, settings: Settings) -> ModelCalls | None:
    """Precision models need the real Claude: the fake (tests, `--fake-claude`) and local mode build none."""
    return ClaudeModelCalls(identifier, settings) if isinstance(identifier, ClaudeIdentifier) else None


def create_app(settings: Settings, detector: Detector, identifier_factory: IdentifierFactory,
               static_dir: Path = Path("web/dist"), faces: FaceFinder | None = None,
               hands: HandFinder | None = None, profiles: ProfileStore | None = None,
               transcriber: Transcriber | None = None, models: ModelStore | None = None,
               compiler: Compiler | None = None,
               model_calls: Callable[[Identifier | None, Settings], ModelCalls | None] = default_model_calls,
               model_notice: str | None = None) -> FastAPI:
    """`profiles`, `models`: the stores shared by every connection; None keeps them in memory (tests). The
    precision model's builder exists when there is a compiler and real Claude; `model_notice` says why not."""
    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.identifier, app.state.notice, app.state.mode = await identifier_factory()
        app.state.active = None
        app.state.budget = SessionBudget()
        app.state.profiles = profiles if profiles is not None else ProfileStore(None)
        app.state.models = models if models is not None else ModelStore(None)
        calls = model_calls(app.state.identifier, settings)
        app.state.builder = (ModelBuilder(settings, calls, compiler, app.state.models, app.state.budget,
                                          CallLog(settings.runs_dir, settings.log_calls))
                             if calls is not None and compiler is not None else None)
        yield
        if app.state.builder is not None:
            await app.state.builder.aclose()

    app = FastAPI(lifespan=lifespan)

    allowed_origins = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")
                       for port in (settings.port, VITE_DEV_PORT)}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        origin = ws.headers.get("origin")
        if origin is not None and origin not in allowed_origins:  # another website must not spend the API key
            await ws.close(code=POLICY_VIOLATION)
            return
        await ws.accept()
        previous, app.state.active = app.state.active, ws
        if previous is not None:
            with contextlib.suppress(Exception):
                await previous.close(code=REPLACED_CODE)
        await asyncio.to_thread(detector.reset)

        identifier: Identifier | None = app.state.identifier
        sender = Sender(ws)
        telemetry = Telemetry(settings, app.state.mode, identifier.model_label if identifier else "–",
                              budget=app.state.budget)
        pipeline = Pipeline(settings, detector, identifier, telemetry, CallLog(settings.runs_dir, settings.log_calls),
                            sender.send, faces=faces, hands=hands, profiles=app.state.profiles,
                            transcriber=transcriber, models=app.state.models, builder=app.state.builder)
        slot = FrameSlot()
        if app.state.notice:
            await sender.send(NoticeMsg(level="warn", text=app.state.notice))
        if model_notice:
            await sender.send(NoticeMsg(level="info", text=model_notice))
        tasks = [asyncio.create_task(pipeline.run(slot)), asyncio.create_task(_tick(pipeline, slot))]
        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if (data := message.get("bytes")) is not None:
                    with contextlib.suppress(FrameFormatError):
                        slot.put(parse_frame_message(data))
                elif (text := message.get("text")) is not None:
                    if (client_message := parse_client_message(text)) is not None:
                        await pipeline.on_client_message(client_message)
        except Exception:  # noqa: BLE001 - a closed or replaced socket ends this connection quietly
            log.debug("websocket closed", exc_info=True)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await pipeline.aclose()
            if app.state.active is ws:
                app.state.active = None

    @app.get("/models/{slug}/{name}")
    async def model_file(slug: str, name: str) -> Response:
        """A part (STL) or the OpenSCAD source of a stored precision model; only what its manifest lists."""
        data = app.state.models.file(slug, name)
        if data is None:
            raise HTTPException(status_code=404)
        kind = "model/stl" if name.endswith(".stl") else "text/plain; charset=utf-8"
        return Response(content=data, media_type=kind)

    if (static_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def not_built() -> str:
            return NOT_BUILT

    return app
