import os
import tempfile
import unittest

os.environ["NOTEBOX_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app as notebox  # noqa: E402


class NoteBoxTests(unittest.TestCase):
    def setUp(self):
        notebox.init_db()
        self.client = notebox.app.test_client()

    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_login_and_list(self):
        r = self.client.post("/login", data={"username": "alice", "password": "alice-test-pw"})
        self.assertEqual(r.status_code, 302)
        self.assertIn(b"Alice shopping", self.client.get("/notes").data)

    def test_wrong_password(self):
        r = self.client.post("/login", data={"username": "alice", "password": "nope"})
        self.assertIn(b"Wrong username", r.data)


if __name__ == "__main__":
    unittest.main()
