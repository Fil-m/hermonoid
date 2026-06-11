"""Hermonoid Server — gonka API chat, self-contained in APK via Chaquopy."""

import json
import os
import socket
import sqlite3
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

PORT = 8080
HOST = "127.0.0.1"

ASSETS_DIR = "/data/data/com.hermonoid.app/files/chaquopy/asset"
DB_DIR = "/data/data/com.hermonoid.app/files"
DB_PATH = os.path.join(DB_DIR, "hermonoid_sessions.db")
CONFIG_PATH = os.path.join(DB_DIR, "hermonoid_config.json")

GONKA_URL = "https://proxy.gonka.gg/v1/chat/completions"
GONKA_MODELS = [
    {"id": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8", "name": "Qwen3 235B", "free": True},
    {"id": "moonshotai/Kimi-K2.6", "name": "Kimi K2.6", "free": True},
    {"id": "MiniMaxAI/MiniMax-M2.7", "name": "MiniMax M2.7", "free": True},
]

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except: pass
    return {"api_key": "", "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8", "base_url": GONKA_URL}

def save_config(cfg):
    os.makedirs(DB_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, title TEXT NOT NULL,
        created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL, role TEXT NOT NULL,
        text TEXT NOT NULL DEFAULT '', media TEXT,
        created_at REAL NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(id))""")
    conn.commit()
    return conn

def create_session(title="Новий чат"):
    sid = uuid.uuid4().hex[:8]
    now = time.time()
    conn = get_db()
    conn.execute("INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                 (sid, title, now, now))
    conn.commit()
    conn.close()
    return sid

def list_sessions():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at, "
        "(SELECT COUNT(*) FROM messages WHERE session_id = id) as msg_count "
        "FROM sessions ORDER BY updated_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_session(sid):
    conn = get_db()
    s = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    conn.close()
    return dict(s) if s else None

def rename_session(sid, title):
    conn = get_db()
    conn.execute("UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                 (title, time.time(), sid))
    conn.commit()
    conn.close()

def delete_session(sid):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
    conn.commit()
    conn.close()

def save_message(sid, role, text, media=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (session_id, role, text, media, created_at) VALUES (?, ?, ?, ?, ?)",
        (sid, role, text, json.dumps(media) if media else None, time.time()))
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (time.time(), sid))
    conn.commit()
    conn.close()

def get_messages(sid, limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT role, text, media, created_at FROM messages "
        "WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
        (sid, limit)).fetchall()
    conn.close()
    result = []
    for r in rows:
        msg = {"role": r["role"], "text": r["text"]}
        if r["media"]:
            try: msg["media"] = json.loads(r["media"])
            except: pass
        result.append(msg)
    return result

def chat_with_api(messages, api_key, model, base_url):
    if not api_key:
        return "❌ API ключ не налаштовано. Відкрий Налаштування."
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "") or "⚠️ Порожня відповідь"
            return "⚠️ Немає choices"
        elif resp.status_code == 401:
            return "❌ Невірний API ключ"
        elif resp.status_code == 402:
            return "❌ Недостатньо коштів"
        else:
            return f"❌ Помилка ({resp.status_code})"
    except requests.exceptions.Timeout:
        return "⏱ Таймаут"
    except requests.exceptions.ConnectionError:
        return "❌ Немає інтернету"
    except Exception as e:
        return f"❌ {str(e)}"

class Handler(BaseHTTPRequestHandler):

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try: return json.loads(self.rfile.read(length))
        except: return {}

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_asset(self, path):
        full = os.path.join(ASSETS_DIR, "web", path.lstrip("/"))
        if not os.path.exists(full) or not os.path.isfile(full):
            # fallback: try without web/ prefix
            full = os.path.join(ASSETS_DIR, path.lstrip("/"))
        if not os.path.exists(full):
            self._json({"error": "Not found"}, 404)
            return
        ext = os.path.splitext(full)[1]
        mime = {".html": "text/html; charset=utf-8", ".css": "text/css",
                ".js": "application/javascript", ".png": "image/png",
                ".jpg": "image/jpeg", ".svg": "image/svg+xml"}.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(full, "rb") as f:
            self.wfile.write(f.read())

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path in ("", "/", "/index.html"):
            self._serve_asset("index.html")
            return
        if path in ("/settings.html", "/settings"):
            self._serve_asset("settings.html")
            return
        if path == "/api/status":
            self._json({"status": "ok", "sessions": len(list_sessions())})
            return
        if path == "/api/sessions":
            self._json({"sessions": list_sessions()})
            return
        if path.startswith("/api/sessions/"):
            parts = path.split("/")
            if len(parts) == 4:
                s = get_session(parts[3])
                if s: self._json({"session": s, "messages": get_messages(parts[3])})
                else: self._json({"error": "Not found"}, 404)
                return
        if path == "/api/config":
            cfg = load_config()
            self._json({
                "api_key": bool(cfg.get("api_key")),
                "model": cfg.get("model", "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"),
                "base_url": cfg.get("base_url", GONKA_URL),
                "models": GONKA_MODELS,
            })
            return
        self._json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        data = self._read_body()

        if path == "/api/chat":
            message = data.get("message", "")
            session_id = data.get("session_id", "")
            history = data.get("history", [])
            if not message:
                self._json({"error": "Message required"}, 400)
                return
            if session_id:
                save_message(session_id, "user", message)
            cfg = load_config()
            api_key = cfg.get("api_key", "")
            model = data.get("model", cfg.get("model", "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"))
            base_url = data.get("base_url", cfg.get("base_url", GONKA_URL))

            msgs = [{"role": "system", "content": "Ти — Hermes Agent, розумний асистент. Відповідай українською."}]
            for h in history[-20:]:
                msgs.append({"role": "user" if h.get("role") == "user" else "assistant", "content": h.get("text", "")})
            msgs.append({"role": "user", "content": message})

            response = chat_with_api(msgs, api_key, model, base_url)

            if session_id:
                save_message(session_id, "assistant", response)
                s = get_session(session_id)
                if s and s["title"] == "Новий чат" and len(message) >= 3:
                    rename_session(session_id, message[:40])
            self._json({"response": response})
            return

        if path == "/api/sessions":
            sid = create_session(data.get("title", "Новий чат"))
            self._json({"session_id": sid, "title": data.get("title", "Новий чат")})
            return

        if path.startswith("/api/sessions/") and path.endswith("/rename"):
            rename_session(path.split("/")[3], data.get("title", "Чат"))
            self._json({"ok": True})
            return

        if path == "/api/settings":
            cfg = load_config()
            for k in ("api_key", "model", "base_url"):
                if k in data:
                    cfg[k] = data[k]
            save_config(cfg)
            self._json({"ok": True})
            return

        self._json({"error": "Not found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path.rstrip("/")
        if path.startswith("/api/sessions/"):
            delete_session(path.split("/")[3])
            self._json({"ok": True})
            return
        self._json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, fmt, *args):
        if "/api/" in str(args):
            print(f"[Hermonoid] {self.command} {args[0]}")

_server = None

def start_server(assets_path, db_dir):
    global _server_instance, ASSETS_DIR, DB_DIR
    ASSETS_DIR = assets_path
    DB_DIR = db_dir
    get_db()
    _server = HTTPServer((HOST, PORT), Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    return PORT

def stop_server():
    global _server
    if _server:
        _server.shutdown()
        _server = None
