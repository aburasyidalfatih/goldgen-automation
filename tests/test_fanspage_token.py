import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from controllers import routes


class FanspageTokenEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "config.json"
        self.config_path.write_text(json.dumps({
            "fanspages": [
                {"name": "Erna Gold", "page_id": "123", "access_token": "EAAB-secret",
                 "token_created_date": "2026-09-01T10:00:00"},
                {"name": "No Token", "page_id": "456"},
            ]
        }))
        self.patcher = patch.object(routes, "CONFIG_PATH", self.config_path)
        self.patcher.start()

        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(routes.bp)
        self.client = app.test_client()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def login(self):
        with self.client.session_transaction() as sess:
            sess["authenticated"] = True

    def test_requires_login(self):
        res = self.client.get("/api/fanspages/123/token")
        self.assertEqual(res.status_code, 401)

    def test_returns_full_token_without_caching(self):
        self.login()
        res = self.client.get("/api/fanspages/123/token")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["access_token"], "EAAB-secret")
        self.assertEqual(res.get_json()["page_id"], "123")
        self.assertEqual(res.headers["Cache-Control"], "no-store")

    def test_page_without_token_returns_empty_string(self):
        self.login()
        res = self.client.get("/api/fanspages/456/token")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["access_token"], "")

    def test_unknown_page_is_404(self):
        self.login()
        res = self.client.get("/api/fanspages/999/token")
        self.assertEqual(res.status_code, 404)

    def test_config_listing_still_hides_token(self):
        self.login()
        with patch.object(routes, "get_db", side_effect=Exception("no db")):
            res = self.client.get("/api/config")
        self.assertNotIn("EAAB-secret", res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
