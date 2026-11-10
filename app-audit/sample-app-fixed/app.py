"""NoteBox - the sample app AFTER the app-audit skill fixed it. See AUDIT.md."""
import logging
import os
import secrets
import sqlite3
import time

from flask import Flask, Response, abort, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
# F-03: secrets come from the environment, never from the code.
app.secret_key = os.environ.get("NOTEBOX_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("NOTEBOX_HTTPS") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
    MAX_CONTENT_LENGTH=64 * 1024,
)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("notebox")

DB_PATH = os.environ.get("NOTEBOX_DB", os.path.join(os.path.dirname(__file__), "notebox.db"))
MAX_FAILS, LOCK_SECONDS = 5, 300
failed_logins = {}  # (ip, username) -> (count, time of last fail). In memory: fine for one small server.


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    """Dev/test data only. Never run this on a real server."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS notes;
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE notes (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                            title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '');
        CREATE INDEX idx_notes_user ON notes(user_id);
        """
    )
    for name, test_pw in (("alice", "alice-test-pw"), ("bob", "bob-test-pw")):
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                     (name, generate_password_hash(test_pw)))
    conn.execute("INSERT INTO notes (user_id, title, body) VALUES (1, 'Alice shopping', 'ALICE-PRIVATE milk, eggs')")
    conn.execute("INSERT INTO notes (user_id, title, body) VALUES (2, 'Bob ideas', 'BOB-PRIVATE build a robot')")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- CSRF (F-06)
def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("csrf_token", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf_token", "")):
            log.warning("csrf check failed path=%s ip=%s", request.path, request.remote_addr)
            abort(400, "Form expired. Go back, reload the page and try again.")


# ---------------------------------------------------------------- security headers (F-09)
@app.after_request
def security_headers(resp):
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if app.config["SESSION_COOKIE_SECURE"]:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if "user_id" in session:
        resp.headers["Cache-Control"] = "no-store"
    return resp


def current_user_id():
    return session.get("user_id")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")[:80]
        typed = request.form.get("password", "")[:200]
        key = (request.remote_addr, username.lower())
        count, last = failed_logins.get(key, (0, 0))
        if count >= MAX_FAILS and time.time() - last < LOCK_SECONDS:  # F-07
            log.warning("login locked user=%r ip=%s", username, request.remote_addr)
            return render_template("login.html", error="Too many tries. Wait 5 minutes."), 429
        # F-01: values are passed as parameters, never put inside the SQL text.
        user = db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], typed):  # F-05
            failed_logins.pop(key, None)
            session.clear()  # new session after login
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session.permanent = True
            log.info("login ok user=%r", username)
            return redirect(url_for("notes"))
        failed_logins[key] = (count + 1 if time.time() - last < LOCK_SECONDS else 1, time.time())
        log.warning("login failed user=%r ip=%s", username, request.remote_addr)
        error = "Wrong username or password"
    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/notes", methods=["GET", "POST"])
def notes():
    if current_user_id() is None:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "")
        if not title or len(title) > 120 or len(body) > 10000:
            abort(400, "Title is needed (max 120 letters). Note max 10000 letters.")
        db().execute("INSERT INTO notes (user_id, title, body) VALUES (?, ?, ?)", (current_user_id(), title, body))
        db().commit()
        return redirect(url_for("notes"))
    q = request.args.get("q", "")[:120]
    rows = db().execute(
        "SELECT * FROM notes WHERE user_id = ? AND title LIKE ?", (current_user_id(), f"%{q}%")
    ).fetchall()
    return render_template("notes.html", notes=rows, q=q)


@app.route("/notes/export")
def export_notes():
    if current_user_id() is None:
        return redirect(url_for("login"))
    rows = db().execute("SELECT title, body FROM notes WHERE user_id = ?", (current_user_id(),)).fetchall()
    text = "\n\n".join(f"# {r['title']}\n{r['body']}" for r in rows)
    return Response(text, mimetype="text/plain",
                    headers={"Content-Disposition": "attachment; filename=notes.txt"})


@app.route("/notes/<int:note_id>")
def note_detail(note_id):
    if current_user_id() is None:
        return redirect(url_for("login"))
    # F-04: the query also checks the owner. Someone else's note looks the same as a missing note.
    note = db().execute("SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, current_user_id())).fetchone()
    if note is None:
        log.warning("note not found or not owned note=%s user=%s", note_id, current_user_id())
        abort(404)
    return render_template("note.html", note=note)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH) and os.environ.get("NOTEBOX_ENV", "dev") == "dev":
        init_db()
    # F-08: debug is off unless you switch it on for yourself.
    app.run(port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("NOTEBOX_DEBUG") == "1")
