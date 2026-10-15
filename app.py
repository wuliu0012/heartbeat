"""Heartbeat public edition. 原创：空气小狗老师. MIT License."""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

BASE = Path(__file__).resolve().parent
ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def settings():
    load_dotenv(BASE / ".env")
    return {"TOKEN": os.getenv("HEARTBEAT_TOKEN", ""),
            "ORIGIN": os.getenv("ALLOWED_ORIGIN", ""),
            "DATA_DIR": os.getenv("DATA_DIR", str(BASE / "data"))}


class Store:
    def __init__(self, directory):
        root = Path(directory).resolve()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = root / "heartbeat.sqlite3"
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, value TEXT NOT NULL, acked INTEGER NOT NULL DEFAULT 0)")
        os.chmod(self.path, 0o600)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def current(db):
        row = db.execute("SELECT value FROM state WHERE id=1").fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def save(db, state):
        db.execute("INSERT OR REPLACE INTO state(id,value) VALUES(1,?)", (json.dumps(state, ensure_ascii=False),))

    def snapshot(self):
        with self.transaction() as db:
            state = self.current(db)
            extra = [json.loads(r[0]) for r in db.execute("SELECT value FROM messages ORDER BY rowid")]
            return state, extra

    def enqueue(self, snapshot, text, now):
        with self.transaction() as db:
            state = self.current(db)
            if not state or any(state[k] != snapshot[k] for k in ("conversation_id", "generation")):
                return None
            # Another worker may have already handled this snapshot.
            if state["last_heartbeat_ts"] != snapshot["last_heartbeat_ts"]:
                return None
            entry = {"id": uuid.uuid4().hex, "conversation_id": state["conversation_id"],
                     "generation": state["generation"], "content": text, "heartbeat": True}
            db.execute("INSERT INTO messages(id,value) VALUES(?,?)", (entry["id"], json.dumps(entry, ensure_ascii=False)))
            state["last_heartbeat_ts"] = now
            self.save(db, state)
            return entry


def matches(state, data):
    return bool(state) and all(state[k] == data.get(k) for k in ("conversation_id", "generation"))


def create_app(config=None):
    os.umask(0o077)
    cfg = settings() if config is None else config
    token, origin = cfg.get("TOKEN", ""), cfg.get("ORIGIN", "")
    parsed = urlsplit(origin)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if len(token) < 32 or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or (parsed.scheme != "https" and not (local and parsed.scheme == "http")):
        raise ValueError("Configure a 32+ character HEARTBEAT_TOKEN and exact HTTPS ALLOWED_ORIGIN (HTTP loopback allowed for local tests)")
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    app.config["PROPAGATE_EXCEPTIONS"] = False
    store = Store(cfg["DATA_DIR"])
    app.extensions["heartbeat_store"] = store

    @app.before_request
    def authorize():
        if request.path in ("/demo", "/demo.js", "/heartbeat-client.js") and request.method == "GET":
            return None
        if not request.path.startswith("/heartbeat-api/"):
            return jsonify(ok=False), 404
        incoming = request.headers.get("Origin", "")
        if incoming not in ("", origin) or (request.method != "GET" and incoming != origin):
            return jsonify(ok=False, error="origin_not_allowed"), 403
        supplied = request.headers.get("X-Heartbeat-Token", "")
        if not hmac.compare_digest(supplied.encode(), token.encode()):
            return jsonify(ok=False, error="unauthorized"), 401

    @app.after_request
    def private(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.errorhandler(Exception)
    def safe_error(error):
        # Do not echo exceptions, payloads, credentials, or model responses.
        from werkzeug.exceptions import HTTPException
        code = error.code if isinstance(error, HTTPException) else 500
        return jsonify(ok=False, error="request_failed"), code

    @app.get("/demo")
    def demo():
        return send_from_directory(BASE / "examples", "index.html")

    @app.get("/heartbeat-client.js")
    def client_script():
        return send_from_directory(BASE / "frontend", "heartbeat-client.js")

    @app.get("/demo.js")
    def demo_script():
        return send_from_directory(BASE / "examples", "demo.js")

    @app.get("/heartbeat-api/status")
    def status():
        state, entries = store.snapshot()
        with store.transaction() as db:
            pending = db.execute("SELECT count(*) FROM messages WHERE acked=0").fetchone()[0]
        return jsonify(ok=True, connected=bool(state), conversation_id=state["conversation_id"] if state else None,
                       history_len=len(state["history"]) if state else 0, pending_count=pending)

    @app.post("/heartbeat-api/sync")
    def sync():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(ok=False, error="invalid_data"), 400
        chat, revision, history = body.get("conversation_id"), body.get("revision"), body.get("history")
        prompt = body.get("system_prompt", "")
        if not isinstance(chat, str) or not ID.fullmatch(chat) or type(revision) is not int or not 0 < revision < 10**17 or not isinstance(history, list) or len(history) > 2000 or not isinstance(prompt, str) or len(prompt) > 32000:
            return jsonify(ok=False, error="invalid_data"), 400
        if any(not isinstance(h, dict) or h.get("role") not in ("user", "ai", "assistant") or not isinstance(h.get("content"), str) for h in history):
            return jsonify(ok=False, error="invalid_history"), 400
        # Accept only documented fields: credentials in cfg are never persisted.
        history = [{"role": h["role"], "content": h["content"]} for h in history]
        stamp = int(time.time() * 1000)
        fingerprint = hashlib.sha256(json.dumps([chat, prompt, history], sort_keys=True).encode()).hexdigest()
        with store.transaction() as db:
            old = store.current(db)
            if old and revision <= old["revision"]:
                return jsonify(ok=False, error="stale_revision"), 409
            changed = not old or old["fingerprint"] != fingerprint
            if changed:
                db.execute("DELETE FROM messages")
            state = dict(conversation_id=chat, revision=revision, history=history, system_prompt=prompt,
                         fingerprint=fingerprint, generation=uuid.uuid4().hex if changed else old["generation"],
                         last_user_ts=stamp if changed else old["last_user_ts"],
                         last_heartbeat_ts=0 if changed else old["last_heartbeat_ts"])
            store.save(db, state)
        return jsonify(ok=True, conversation_id=chat, generation=state["generation"])

    @app.get("/heartbeat-api/pull")
    def pull():
        with store.transaction() as db:
            state = store.current(db)
            if not matches(state, request.args):
                return jsonify(ok=False, error="stale_context"), 409
            entries = [json.loads(r[0]) for r in db.execute("SELECT value FROM messages WHERE acked=0 ORDER BY rowid")]
        return jsonify(ok=True, conversation_id=state["conversation_id"], generation=state["generation"], entries=entries)

    @app.post("/heartbeat-api/ack")
    @app.post("/heartbeat-api/touch")
    def mutate():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(ok=False), 400
        with store.transaction() as db:
            state = store.current(db)
            if not matches(state, body):
                return jsonify(ok=False, error="stale_context"), 409
            if request.path.endswith("/touch"):
                state["last_user_ts"] = int(time.time()*1000)
                store.save(db, state)
            else:
                ids = body.get("ids", [])
                if not isinstance(ids, list) or len(ids) > 1000 or any(not isinstance(i, str) for i in ids):
                    return jsonify(ok=False), 400
                db.executemany("UPDATE messages SET acked=1 WHERE id=?", [(i,) for i in ids])
        return jsonify(ok=True)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5051")), debug=False)
