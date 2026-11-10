"""NoteBox - a tiny notes app used to test the app-audit skill.

WARNING: this app has security bugs ON PURPOSE. Never deploy it.
The planted bugs are listed in ../README.md.
"""
import os
import sqlite3

from flask import Flask, g, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "notebox-super-secret-key-2024"
PAYMENT_API_KEY = "nbx_live_4f9a1c7e2b8d4a6f9c3e51d07b2a"

DB_PATH = os.environ.get("NOTEBOX_DB", os.path.join(os.path.dirname(__file__), "notebox.db"))


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
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS notes;
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT);
        CREATE TABLE notes (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, body TEXT);
        INSERT INTO users (username, password) VALUES ('alice', 'alice-test-pw');
        INSERT INTO users (username, password) VALUES ('bob', 'bob-test-pw');
        INSERT INTO notes (user_id, title, body) VALUES (1, 'Alice shopping', 'ALICE-PRIVATE milk, eggs');
        INSERT INTO notes (user_id, title, body) VALUES (2, 'Bob ideas', 'BOB-PRIVATE build a robot');
        """
    )
    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        user = db().execute(query).fetchone()
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("notes"))
        error = "Wrong username or password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/notes", methods=["GET", "POST"])
def notes():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        db().execute(
            "INSERT INTO notes (user_id, title, body) VALUES (?, ?, ?)",
            (session["user_id"], request.form.get("title", ""), request.form.get("body", "")),
        )
        db().commit()
        return redirect(url_for("notes"))
    q = request.args.get("q", "")
    rows = db().execute(
        "SELECT * FROM notes WHERE user_id = ? AND title LIKE ?",
        (session["user_id"], f"%{q}%"),
    ).fetchall()
    return render_template("notes.html", notes=rows, q=q)


@app.route("/notes/<int:note_id>")
def note_detail(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    note = db().execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if note is None:
        return "Note not found", 404
    return render_template("note.html", note=note)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(port=int(os.environ.get("PORT", "5000")), debug=True)
