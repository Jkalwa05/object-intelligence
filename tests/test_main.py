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
