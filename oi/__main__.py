"""Start Object Intelligence: `uv run python -m oi [--port 8766] [--fake-claude] [--no-browser]`."""

from __future__ import annotations

import argparse
import logging
import threading
import webbrowser
from dataclasses import replace
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from oi.config import Settings
from oi.identify import choose_identifier
from oi.perception import YoloeDetector
from oi.server import create_app


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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    detector = YoloeDetector(settings)
    app = create_app(settings, detector, lambda: choose_identifier(settings, args.fake_claude))
    url = f"http://127.0.0.1:{port}"
    print(f"Object Intelligence: {url}  (Detektor {detector.model_name}, Modell "
          f"{'fake' if args.fake_claude else settings.model})")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
