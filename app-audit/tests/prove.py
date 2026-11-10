#!/usr/bin/env python3
"""Proof that the skill's scripts find the six planted bugs in the sample app.

  python tests/prove.py                      -> sample-app must show ALL six bugs
  python tests/prove.py sample-app-fixed --expect fixed
                                             -> fixed copy must show NONE of them

Starts the app on a free port with a fresh test database, runs every helper
script, then reads their JSON output.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, ".claude", "skills", "app-audit", "scripts")
PY = sys.executable


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run(script, *args, env=None):
    r = subprocess.run([PY, os.path.join(SK, script), *args], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit(f"{script} crashed")


def load(out, name):
    with open(os.path.join(out, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app", nargs="?", default="sample-app")
    ap.add_argument("--expect", choices=["bugs", "fixed"], default="bugs")
    args = ap.parse_args()
    app_dir = os.path.join(ROOT, args.app)
    out = tempfile.mkdtemp(prefix="app-audit-prove-")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, PORT=str(port), NOTEBOX_DB=os.path.join(out, "prove.db"),
               NOTEBOX_SECRET_KEY="prove-run-only-key-not-a-real-secret", NOTEBOX_NO_RELOAD="1",
               AUDIT_PASSWORD="alice-test-pw", AUDIT_PASSWORD_A="alice-test-pw", AUDIT_PASSWORD_B="bob-test-pw")
    server = subprocess.Popen([PY, "app.py"], cwd=app_dir, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(base + "/", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        else:
            raise SystemExit("sample app did not start")

        run("map_app.py", app_dir, "--out", out)
        run("scan_code.py", app_dir, "--out", out)
        run("click_audit.py", "--base", base, "--login-url", "/login", "--username", "alice", "--out", out, env=env)
        run("access_check.py", "--base", base, "--login", "/login", "--user-a", "alice", "--user-b", "bob",
            "--paths", "/notes/1", "--out", out, env=env)
        run("probe_inputs.py", "--base", base, "--path", "/login", "--method", "POST",
            "--params", "username", "password", "--out", out, env=env)
        run("probe_inputs.py", "--base", base, "--path", "/notes", "--params", "q",
            "--login", "/login", "--user", "alice", "--out", out, env=env)
        run("probe_inputs.py", "--base", base, "--path", "/notes", "--method", "POST", "--params", "title", "body",
            "--login", "/login", "--user", "alice", "--out", out, env=env)
        run("check_http.py", "--base", base, "--paths", "/", "/login", "--login", "/login", "--user", "alice",
            "--out", out, env=env)
    finally:
        try:  # stop the server and any child it started (Flask debug reloader)
            os.killpg(server.pid, 15)
        except (AttributeError, ProcessLookupError, PermissionError):
            server.terminate()

    ui = load(out, "ui_table.json")["rows"]
    code = load(out, "code_scan.json")["hits"]
    access = load(out, "access_check.json")
    p_login = load(out, "probe_POST_login.json")
    p_search = load(out, "probe_GET_notes.json")
    p_note = load(out, "probe_POST_notes.json")

    def both(word):
        return {r["viewport"] for r in ui if word in r["status"]}

    found = {
        "1 dead button (click test)": bool(both("dead button")),
        "2 duplicate button (click test)": bool(both("duplicate")),
        "3 SQL injection (code scan)": any(h["id"] == "SQLI" for h in code),
        "3 SQL injection (confirmed live on login)": any("SQL injection" in r["verdict"] and "FAIL" in r["verdict"] for r in p_login),
        "4 XSS (code scan)": any(h["id"] == "XSS" for h in code),
        "4 XSS reflected (confirmed live on search)": any("XSS CONFIRMED" in r["verdict"] for r in p_search),
        "4 XSS stored (confirmed live on note body)": any("XSS CONFIRMED" in r["verdict"] for r in p_note),
        "5 missing access check (user B reads A's note)": any(r["verdict"].startswith("FAIL") for r in access),
        "6 secret in code (code scan)": any(h["id"] == "SECRET" and h["severity"] == "critical" for h in code),
    }
    want = args.expect == "bugs"
    print(f"\nApp: {args.app}   expecting: {'all planted bugs FOUND' if want else 'all planted bugs GONE'}\n")
    ok = True
    for name, hit in found.items():
        good = hit == want
        ok &= good
        print(f"  [{'OK ' if good else 'BAD'}] {name}: {'found' if hit else 'not found'}")
    if want:
        sizes = both("dead button") & both("duplicate")
        size_ok = sizes == {"desktop-1440", "phone-390"}
        ok &= size_ok
        print(f"  [{'OK ' if size_ok else 'BAD'}] UI bugs seen at both screen sizes: {sorted(sizes)}")
    print(f"\nRaw output: {out}")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
