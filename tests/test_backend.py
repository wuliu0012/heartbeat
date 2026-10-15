"""All fixtures synthetic. Never load a user's .env, talk to a model, or send push."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from worker import tick, generate, notify

ORIGIN = "https://example.invalid"
TOKEN = "synthetic-test-token-" * 3


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({"TOKEN": TOKEN, "ORIGIN": ORIGIN, "DATA_DIR": self.temp.name})
        self.client = self.app.test_client()
        self.store = self.app.extensions["heartbeat_store"]
        self.headers = {"Origin": ORIGIN, "X-Heartbeat-Token": TOKEN}

    def tearDown(self):
        self.temp.cleanup()

    def sync(self, chat="first", revision=1, text="Synthetic selected message", **extra):
        return self.client.post("/heartbeat-api/sync", headers=self.headers,
                                json=dict(conversation_id=chat, revision=revision,
                                          history=[{"role": "user", "content": text}], **extra))

    def test_auth_and_validation(self):
        self.assertEqual(self.client.get("/heartbeat-api/status").status_code, 401)
        self.assertEqual(self.client.get("/heartbeat-api/status", headers={**self.headers, "Origin": "https://other.invalid"}).status_code, 403)
        self.assertEqual(self.client.post("/heartbeat-api/sync", headers={"X-Heartbeat-Token": TOKEN}, json={}).status_code, 403)
        for body in ([], None, {"conversation_id": "x", "revision": True, "history": []}):
            self.assertEqual(self.client.post("/heartbeat-api/sync", headers=self.headers, json=body).status_code, 400)
        self.assertEqual(self.client.get("/heartbeat-api/status", headers={"X-Heartbeat-Token": TOKEN}).status_code, 200)

    def test_stale_and_scoped_delivery(self):
        state = self.sync().json
        snap, _ = self.store.snapshot()
        entry = self.store.enqueue(snap, "Synthetic heartbeat", 123)
        scope = {"conversation_id": "first", "generation": state["generation"]}
        for _ in range(2):
            result = self.client.get("/heartbeat-api/pull", headers=self.headers, query_string=scope)
            self.assertEqual(result.json["entries"], [entry])
        self.assertEqual(self.sync(revision=1).status_code, 409)
        self.assertEqual(self.sync(revision=2).json["generation"], scope["generation"])
        wrong = {**scope, "conversation_id": "other", "ids": [entry["id"]]}
        self.assertEqual(self.client.post("/heartbeat-api/ack", headers=self.headers, json=wrong).status_code, 409)
        self.assertEqual(self.client.post("/heartbeat-api/ack", headers=self.headers, json={**scope, "ids": [entry["id"]]}).status_code, 200)
        self.assertEqual(self.client.get("/heartbeat-api/pull", headers=self.headers, query_string=scope).json["entries"], [])
        self.sync(chat="second", revision=3)
        self.assertEqual(self.client.get("/heartbeat-api/pull", headers=self.headers, query_string=scope).status_code, 409)
        self.assertIsNone(self.store.enqueue(snap, "Late result", 124))

    def test_no_client_credentials_persisted_or_returned(self):
        self.sync(cfg={"apiKey": "synthetic-do-not-persist"})
        state, _ = self.store.snapshot()
        self.assertNotIn("cfg", state)
        self.assertNotIn("synthetic-do-not-persist", str(state))
        status = self.client.get("/heartbeat-api/status", headers=self.headers).json
        self.assertNotIn("history", status)
        self.assertNotIn("system_prompt", status)

    def test_generation_race_and_silence(self):
        self.assertEqual(tick(self.store, threshold=0), "no_context")
        self.sync()
        called = []
        def race(*args):
            self.sync(chat="second", revision=2)
            return "Obsolete result"
        self.assertEqual(tick(self.store, generate_fn=race, notify_fn=lambda e: called.append(e), threshold=0), "obsolete_generation")
        self.assertFalse(called)
        self.assertEqual(tick(self.store, generate_fn=lambda *a: "<SILENCE/>", threshold=0), "silent")
        self.assertEqual(tick(self.store, generate_fn=lambda *a: "New result", notify_fn=lambda e: True, threshold=0), "queued_notified")
        self.assertEqual(tick(self.store, threshold=60), "not_due")

    def test_push_failure_keeps_queue(self):
        self.sync()
        def failure(_):
            raise RuntimeError("Synthetic provider failure")
        self.assertEqual(tick(self.store, generate_fn=lambda *a: "Queued result", notify_fn=failure, threshold=0), "queued_only")
        with self.store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM messages WHERE acked=0").fetchone()[0], 1)

    def test_model_and_push_adapters_with_mock_http(self):
        self.sync(system_prompt="Synthetic instruction")
        state, _ = self.store.snapshot()
        env = {"LLM_API_KEY": "synthetic-model-key", "LLM_MODEL": "test-model", "LLM_BASE_URL": "https://model.example.invalid/v1", "BARK_KEY": "synthetic-push-key"}
        with patch.dict("os.environ", env), patch("worker.requests.post") as post:
            post.return_value.json.return_value = {"choices": [{"message": {"content": "Synthetic result"}}]}
            self.assertEqual(generate(state, []), "Synthetic result")
            self.assertTrue(post.call_args.args[0].endswith("/v1/chat/completions"))
            post.return_value.json.return_value = {"code": 200}
            self.assertTrue(notify({"content": "Synthetic notification"}))

    def test_demo_serving_and_fail_closed(self):
        for path in ("/demo", "/demo.js", "/heartbeat-client.js"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertIn("no-store", r.headers["Cache-Control"])
            r.close()
        self.assertNotEqual(self.client.get("/.env").status_code, 200)
        with self.assertRaises(ValueError):
            create_app({"TOKEN": "weak", "ORIGIN": ORIGIN, "DATA_DIR": self.temp.name})


if __name__ == "__main__":
    unittest.main()
