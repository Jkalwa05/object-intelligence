import socket
import threading
import time

from oi.__main__ import open_browser_when_ready


def test_browser_opens_only_once_the_server_listens():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    server = socket.socket()

    def listen_later():
        time.sleep(0.3)
        server.bind(("127.0.0.1", port))
        server.listen()

    threading.Thread(target=listen_later).start()
    opened, started = [], time.monotonic()
    open_browser_when_ready(f"http://127.0.0.1:{port}", port, opener=opened.append, timeout_s=5.0)
    server.close()
    assert opened == [f"http://127.0.0.1:{port}"] and time.monotonic() - started >= 0.3


def test_refuses_to_start_when_the_port_is_busy(monkeypatch, capsys):
    import oi.__main__ as entry
    import pytest

    def no_detector(*args, **kwargs):
        raise AssertionError("the model must not load when the port is taken")

    monkeypatch.setattr(entry, "YoloeDetector", no_detector)
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen()
    port = busy.getsockname()[1]
    with pytest.raises(SystemExit) as stopped:
        entry.main(["--port", str(port), "--no-browser"])
    busy.close()
    assert stopped.value.code == 1
    assert f"Port {port}" in capsys.readouterr().out
