"""Start Object Intelligence: `uv run python -m oi [--port 8766] [--fake-claude] [--no-browser]`."""

from __future__ import annotations

import argparse
import logging
import socket
import threading
import time
import webbrowser
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from oi.config import Settings
from oi.faces import FaceFinder, ensure_model
from oi.identify import choose_identifier
from oi.perception import YoloeDetector
from oi.server import create_app


def open_browser_when_ready(url: str, port: int, opener: Callable[[str], object] = webbrowser.open,
                            timeout_s: float = 60.0) -> None:
    """Wait until the server accepts connections (after the model load and the Claude probe), then open the page."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                opener(url)
                return
        except OSError:
            time.sleep(0.1)


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m oi", description="Object Intelligence: see and identify.")
    parser.add_argument("--port", type=int, default=None, help="default 8766 (OI_PORT)")
    parser.add_argument("--fake-claude", action="store_true", help="free canned answers instead of real Claude calls")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)

    load_dotenv(Path(".env"), override=False)
    settings = Settings.from_env()
    if args.port:
        settings = replace(settings, port=args.port)
    port = settings.port
    if port_in_use(port):  # otherwise the browser would open an older server that is still running
        print(f"Port {port} ist belegt: Läuft schon ein Object-Intelligence-Server? Beende ihn mit Ctrl+C "
              f"oder `lsof -ti tcp:{port} | xargs kill`, dann starte neu.")
        raise SystemExit(1)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    detector = YoloeDetector(settings)
    faces = FaceFinder(ensure_model())  # the privacy veto needs it; no face model, no start
    app = create_app(settings, detector, lambda: choose_identifier(settings, args.fake_claude), faces=faces)
    url = f"http://127.0.0.1:{port}"
    print(f"Object Intelligence: {url}  (Detektor {detector.model_name}, Modell "
          f"{'fake' if args.fake_claude else settings.model})")
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url, port), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
