import http.client
import json
import re
import socket
import threading
import time

import pytest

from cct import paths
from cct.commands import web as web_cmd
from cct.errors import CctError
from cct.services.sessions import save_session
from cct.web import server as web_server
from cct.web.server import HOST, create_server, load_page
from helpers import posix_only, write_usage


@pytest.fixture
def dashboard(cfg):
    server = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def get(server, path="/", host="default"):
    port = server.server_address[1]
    conn = http.client.HTTPConnection(HOST, port, timeout=5)
    conn.putrequest("GET", path, skip_host=True)
    if host == "default":
        host = f"127.0.0.1:{port}"
    if host is not None:
        conn.putheader("Host", host)
    conn.endheaders()
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp, body


def test_binds_to_loopback_only(dashboard):
    assert dashboard.server_address[0] == "127.0.0.1"


def test_page_has_security_headers_and_matching_nonce(dashboard):
    resp, body = get(dashboard)
    assert resp.status == 200
    assert resp.getheader("Content-Type") == "text/html; charset=utf-8"
    assert resp.getheader("Cache-Control") == "no-store"
    assert resp.getheader("X-Content-Type-Options") == "nosniff"
    csp = resp.getheader("Content-Security-Policy")
    assert "default-src 'none'" in csp and "connect-src 'self'" in csp and "form-action 'none'" in csp
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    html = body.decode("utf-8")
    assert f'<script nonce="{nonce}">' in html
    assert "__NONCE__" not in html
    assert "<title>Claude accounts</title>" in html


def test_localhost_host_is_allowed(dashboard):
    port = dashboard.server_address[1]
    assert get(dashboard, host=f"localhost:{port}")[0].status == 200


@pytest.mark.parametrize("host", ["evil.example", "evil.example:{port}", "127.0.0.1:1", "localhost", "", None])
def test_other_hosts_are_refused(dashboard, host):
    """Blocks DNS rebinding: a foreign page can't read the data through its own domain name."""
    if host is not None:
        host = host.format(port=dashboard.server_address[1])
    resp, _ = get(dashboard, "/api/status", host=host)
    assert resp.status == 403


def test_status_api(dashboard, work):
    now = time.time()
    write_usage("main", five=(42, now + 100), seven=(7, now + 1000), updated_at=now)
    save_session(str(work), "abcdef123456", "main", now)
    resp, body = get(dashboard, "/api/status")
    assert resp.status == 200
    assert resp.getheader("Content-Type") == "application/json"
    data = json.loads(body)
    assert set(data) == {"now", "host", "accounts", "sessions"}
    assert data["accounts"][0]["name"] == "main"
    assert data["accounts"][0]["five_hour"]["pct"] == 42
    assert data["sessions"] == [{"folder": str(work), "account": "main", "updated_at": now, "session": "abcdef12"}]


def test_status_api_skips_damaged_session_files(dashboard, work):
    from cct.utils.fs import write_json

    write_json(paths.session_dir() / "damaged.json", {"folder": "/x", "session_id": 12345, "updated_at": 1})
    save_session(str(work), "good-session", "main", time.time())
    resp, body = get(dashboard, "/api/status")
    assert resp.status == 200
    assert [s["session"] for s in json.loads(body)["sessions"]] == ["good-ses"]


def test_status_api_is_strict_json_with_damaged_usage_file(dashboard):
    """Python writes NaN and Infinity into JSON; the browser's JSON.parse rejects them."""
    paths.usage_dir().mkdir(parents=True)
    (paths.usage_dir() / "main.json").write_text(
        '{"updated_at": NaN, "five_hour": {"pct": Infinity}, "seven_day": {"pct": 1, "resets_at": -Infinity}}',
        encoding="utf-8",
    )
    resp, body = get(dashboard, "/api/status")
    assert resp.status == 200

    def refuse(constant):
        raise AssertionError(f"not valid JSON for a browser: {constant}")

    main = json.loads(body, parse_constant=refuse)["accounts"][0]
    assert main["updated_at"] is None
    assert main["five_hour"] == {"state": "unknown"}
    assert main["seven_day"] == {"state": "ok", "pct": 1, "resets_at": None}


def test_query_string_is_ignored(dashboard):
    assert get(dashboard, "/api/status?t=123")[0].status == 200


@pytest.mark.parametrize("path", ["/nope", "/api", "/api/status/", "/static/index.html", "/../config.json"])
def test_unknown_paths_are_404(dashboard, path):
    assert get(dashboard, path)[0].status == 404


def test_write_methods_are_not_supported(dashboard):
    conn = http.client.HTTPConnection(HOST, dashboard.server_address[1], timeout=5)
    conn.request("POST", "/api/status", body="{}", headers={"Host": f"127.0.0.1:{dashboard.server_address[1]}"})
    assert conn.getresponse().status == 501
    conn.close()


def test_broken_config_gives_json_error(dashboard):
    paths.config_file().write_text("{", encoding="utf-8")
    resp, body = get(dashboard, "/api/status")
    assert resp.status == 500
    assert "not valid JSON" in json.loads(body)["error"]


def test_each_start_gets_a_new_nonce():
    assert load_page("aaa") != load_page("bbb")
    assert b'nonce="aaa"' in load_page("aaa")


@pytest.mark.parametrize("result", [None, FileNotFoundError("gone")])
def test_missing_page_is_a_user_error(monkeypatch, result):
    def fake_get_data(package, resource):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(web_server.pkgutil, "get_data", fake_get_data)
    with pytest.raises(CctError, match="Reinstall cct"):
        load_page("n")


@posix_only  # Windows lets a second socket share the port (SO_REUSEADDR), so there is no error to see
def test_port_in_use_is_a_user_error(cfg):
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    try:
        with pytest.raises(CctError, match=f"Can't use port {port}.*cct web --port {port + 1}"):
            create_server(port)
    finally:
        blocker.close()


# ------------------------------------------------------------------ cmd_web


class FakeServer:
    server_address = ("127.0.0.1", 8765)

    def __init__(self):
        self.closed = False

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


@pytest.mark.parametrize("open_browser", [True, False])
def test_cmd_web_prints_url_opens_browser_and_stops_cleanly(cfg, monkeypatch, capsys, open_browser):
    fake, opened = FakeServer(), []
    monkeypatch.setattr(web_cmd, "create_server", lambda port: fake)
    monkeypatch.setattr(web_cmd.webbrowser, "open", opened.append)
    assert web_cmd.cmd_web(8765, open_browser) == 0
    out = capsys.readouterr().out
    assert "cct: dashboard at http://127.0.0.1:8765/  (Ctrl+C to stop)" in out
    assert "cct: stopped." in out
    assert fake.closed
    assert opened == (["http://127.0.0.1:8765/"] if open_browser else [])


def test_cmd_web_fails_early_on_broken_config(monkeypatch):
    paths.config_file().parent.mkdir(parents=True)
    paths.config_file().write_text("{", encoding="utf-8")
    monkeypatch.setattr(web_cmd, "create_server", lambda port: pytest.fail("server must not start"))
    with pytest.raises(CctError):
        web_cmd.cmd_web(8765, False)
