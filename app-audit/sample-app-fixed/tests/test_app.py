import os
import re
import tempfile
import unittest

os.environ["NOTEBOX_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app as notebox  # noqa: E402


class NoteBoxTests(unittest.TestCase):
    def setUp(self):
        notebox.init_db()
        notebox.failed_logins.clear()
        self.client = notebox.app.test_client()

    def token(self, path="/login"):
        html = self.client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def login(self, user, test_pw):
        return self.client.post("/login", data={"username": user, "password": test_pw, "csrf_token": self.token()})

    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_login_and_list(self):
        self.assertEqual(self.login("alice", "alice-test-pw").status_code, 302)
        self.assertIn(b"Alice shopping", self.client.get("/notes").data)

    def test_wrong_password(self):
        self.assertIn(b"Wrong username", self.login("alice", "nope").data)

    # --- one test per fixed finding ---------------------------------
    def test_f01_sql_injection_cannot_log_in(self):
        r = self.login("alice' OR '1'='1' -- ", "x")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Wrong username", r.data)
        self.assertEqual(self.login("x", "' OR '1'='1").status_code, 200)

    def test_f02_xss_is_escaped(self):
        self.login("alice", "alice-test-pw")
        r = self.client.get("/notes?q=<script>alert(1)</script>")
        self.assertNotIn(b"<script>alert(1)</script>", r.data)
        self.client.post("/notes", data={"title": "t", "body": "<img src=x onerror=alert(1)>",
                                         "csrf_token": self.token("/notes")})
        self.assertNotIn(b"<img src=x", self.client.get("/notes/3").data)

    def test_f04_other_users_note_is_hidden(self):
        self.login("bob", "bob-test-pw")
        r = self.client.get("/notes/1")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b"ALICE-PRIVATE", r.data)
        self.assertEqual(self.client.get("/notes/2").status_code, 200)

    def test_f05_passwords_are_hashed(self):
        import sqlite3
        rows = sqlite3.connect(os.environ["NOTEBOX_DB"]).execute("SELECT password_hash FROM users").fetchall()
        for (value,) in rows:
            self.assertNotIn("test-pw", value)

    def test_f06_post_without_csrf_token_is_refused(self):
        self.login("alice", "alice-test-pw")
        self.assertEqual(self.client.post("/notes", data={"title": "x"}).status_code, 400)
        self.assertEqual(self.client.get("/logout").status_code, 405)

    def test_f07_login_locks_after_five_fails(self):
        for _ in range(5):
            self.assertEqual(self.login("alice", "bad").status_code, 200)
        self.assertEqual(self.login("alice", "alice-test-pw").status_code, 429)

    def test_logout_button_ends_the_session(self):
        self.login("alice", "alice-test-pw")
        r = self.client.post("/logout", data={"csrf_token": self.token("/notes")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/notes").status_code, 302)  # sent back to login

    def test_f09_security_headers(self):
        h = self.client.get("/").headers
        self.assertIn("default-src 'self'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")

    def test_export_button_works(self):
        self.login("alice", "alice-test-pw")
        r = self.client.get("/notes/export")
        self.assertIn(b"Alice shopping", r.data)
        self.assertNotIn(b"BOB-PRIVATE", r.data)


if __name__ == "__main__":
    unittest.main()
