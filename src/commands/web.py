"""cct web: the read-only usage page on 127.0.0.1."""

from __future__ import annotations

import webbrowser

from cct.services.config import load_config
from cct.web.server import create_server


def cmd_web(port: int, open_browser: bool) -> int:
    load_config()  # fail early on a broken config
    server = create_server(port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"cct: dashboard at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ncct: stopped.")
    finally:
        server.server_close()
    return 0
