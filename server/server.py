#!/data/data/com.termux/files/home/.venv/bin/python
"""
Hermonoid Chat Server — веб-чат + REST API для Hermes Agent
=============================================================

API endpoints:
  Веб-інтерфейс:
    GET  /                    — веб-чат (index.html)
    GET  /index.html           — те саме

  Сесії (основні):
    GET  /api/status           — статус сервера
    GET  /api/sessions         — список всіх сесій
    POST /api/sessions         — створити нову сесію
    GET  /api/sessions/:id     — сесія + повідомлення
    POST /api/sessions/:id/rename — перейменувати
    DELETE /api/sessions/:id   — видалити сесію

  Чат (основний):
    POST /api/chat             — надіслати повідомлення
    POST /api/exec             — виконати shell команду

  REST API v1 (для зовнішніх програм):
    GET  /api/v1/models        — список доступних моделей
    POST /api/v1/chat/completions — OpenAI-сумісний чат
    POST /api/v1/execute       — виконати команду
    GET  /api/v1/status        — статус сервера
    GET  /api/v1/sessions      — список сесій
"""

import http.server
import json
import os
import socket
import subprocess
import sqlite3
import uuid
import hashlib
import hmac
import time
import threading
import re
from urllib.parse import urlparse, parse_qs

PORT = 8080
HOST = "0.0.0.0"
HERMES_BIN = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
DB_PATH = os.path.expanduser("~/hermonoid/sessions.db")

# ====== API КЛЮЧІ ======

API_KEYS = {}

def load_api_keys():
    key_file = os.path.expanduser("~/hermonoid/config/api_keys.json")
    env_key = os.environ.get("HERMONOID_API_KEY", "")
    if env_key:
        API_KEYS[env_key] = {"name": "default", "permissions": ["chat", "exec", "admin"]}
    if os.path.exists(key_file):
        try:
            with open(key_file) as f:
                API_KEYS.update(json.load(f))
        except:
            pass

load_api_keys()

def check_auth(headers):
    """Перевірити авторизацію. Повертає dict з правами або None."""
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        key = auth[7:]
        if key in API_KEYS:
            return API_KEYS[key]
    xkey = headers.get("X-API-Key", "")
    if xkey in API_KEYS:
        return API_KEYS[xkey]
    # Без ключів — анонімний доступ (тільки чат)
    if not API_KEYS:
        return {"name": "anonymous", "permissions": ["chat", "exec", "admin"]}
    return None

# ====== SQLite СХОВИЩЕ ======

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
    conn.execute("""CREATE TABLE IF NOT EXISTS hermes_sessions (
        web_session_id TEXT PRIMARY KEY,
        hermes_session_id TEXT NOT NULL, created_at REAL NOT NULL,
        FOREIGN KEY (web_session_id) REFERENCES sessions(id))""")
    conn.commit()
    return conn

def create_session(title="Новий чат"):
    sid = str(uuid.uuid4())[:8]
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
        "FROM sessions ORDER BY updated_at DESC LIMIT 50"
    ).fetchall()
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
    conn.execute("DELETE FROM hermes_sessions WHERE web_session_id = ?", (sid,))
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
            msg["media"] = json.loads(r["media"])
        result.append(msg)
    return result

def get_or_create_hermes_session(web_sid):
    conn = get_db()
    row = conn.execute(
        "SELECT hermes_session_id FROM hermes_sessions WHERE web_session_id = ?",
        (web_sid,)).fetchone()
    if row:
        conn.close()
        return row["hermes_session_id"]
    hermes_sid = str(uuid.uuid4())[:12]
    conn.execute(
        "INSERT INTO hermes_sessions (web_session_id, hermes_session_id, created_at) VALUES (?, ?, ?)",
        (web_sid, hermes_sid, time.time()))
    conn.commit()
    conn.close()
    return hermes_sid

def delete_hermes_session(web_sid):
    conn = get_db()
    conn.execute("DELETE FROM hermes_sessions WHERE web_session_id = ?", (web_sid,))
    conn.commit()
    conn.close()

# ====== INTEGRATION ======

def chat_with_hermes(message, session_id=None, history=None):
    try:
        cmd = [HERMES_BIN, "chat", "-q", message, "--quiet"]
        if session_id:
            # Перевіряємо чи це реальна сесія Hermes CLI
            check = subprocess.run([HERMES_BIN, "sessions", "list"], capture_output=True, text=True, timeout=10)
            if session_id in check.stdout:
                cmd.extend(["--resume", session_id])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                                env={**os.environ, "TERM": "xterm-256color"})
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        elif result.stderr.strip():
            return f"⚠️ {result.stderr.strip()}"
        return "❌ Немає відповіді"
    except subprocess.TimeoutExpired:
        return "⏱ Timeout (180s)"
    except Exception as e:
        return f"❌ {str(e)}"

def exec_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = ""
        if result.stdout: output += result.stdout
        if result.stderr: output += f"\n[stderr]\n{result.stderr}"
        if not output.strip(): output = f"✅ Exit code: {result.returncode}"
        return output.strip()
    except subprocess.TimeoutExpired:
        return "⏱ Timeout"
    except Exception as e:
        return f"❌ {str(e)}"

# ====== СЕРВЕР ======

def route(path):
    """Розпарсити шлях і повернути (base, params)"""
    parsed = urlparse(path)
    base = parsed.path.rstrip("/")
    qs = parse_qs(parsed.query)
    return base, {k: v[0] for k, v in qs.items()}

class ChatHandler(http.server.BaseHTTPRequestHandler):

    # ====== GET ======
    def do_GET(self):
        base, qs = route(self.path)

        # Веб-інтерфейс
        if base in ("", "/", "/index.html"):
            self.serve_file(os.path.join(os.path.dirname(__file__), "..", "web", "index.html"), "text/html; charset=utf-8")
            return

        # API v1
        if base == "/api/v1/models":
            return self.json_ok({"object": "list", "data": [
                {"id": "hermes-deepseek", "object": "model", "created": int(time.time()), "owned_by": "hermes"},
                {"id": "hermes-any", "object": "model", "created": int(time.time()), "owned_by": "hermes"},
            ]})

        if base == "/api/v1/status":
            s = list_sessions()
            return self.json_ok({"status": "ok", "sessions": len(s), "models": 2})

        if base == "/api/v1/sessions":
            auth = check_auth(self.headers)
            if not auth: return self.json_error("Unauthorized", 401)
            return self.json_ok({"sessions": list_sessions()})

        # Основні API
        if base == "/api/status":
            return self.json_ok({"status": "ok", "sessions": len(list_sessions())})

        if base == "/api/sessions":
            return self.json_ok({"sessions": list_sessions()})

        # GET /api/sessions/:id
        if base.startswith("/api/sessions/"):
            parts = base.split("/")
            if len(parts) == 4:
                sid = parts[3]
                session = get_session(sid)
                if session:
                    return self.json_ok({"session": session, "messages": get_messages(sid)})
                return self.json_error("Not found", 404)
            if len(parts) == 5 and parts[4] == "messages":
                return self.json_ok({"messages": get_messages(parts[3])})

        self.json_error("Not found", 404)

    # ====== POST ======
    def do_POST(self):
        base, qs = route(self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        data = {}
        if body:
            try: data = json.loads(body)
            except: return self.json_error("Invalid JSON", 400)

        # === API v1: chat completions (OpenAI-compatible) ===
        if base == "/api/v1/chat/completions":
            auth = check_auth(self.headers)
            if not auth: return self.json_error("Unauthorized", 401)
            if "exec" not in auth.get("permissions", []) and "chat" not in auth.get("permissions", []):
                return self.json_error("Forbidden", 403)

            messages = data.get("messages", [])
            model = data.get("model", "hermes-deepseek")
            stream = data.get("stream", False)
            session_id = data.get("session_id", "")

            if not messages:
                return self.json_error("Messages required", 400)

            # Збираємо повідомлення в промпт
            last_msg = messages[-1].get("content", "")
            prompt = f"[{data.get('user', 'API')}]: {last_msg}"

            # Історія як контекст
            if len(messages) > 1:
                history_lines = []
                for m in messages[:-1]:
                    role = "Користувач" if m["role"] in ("user", "system") else "Асистент"
                    history_lines.append(f"{role}: {m.get('content', '')}")
                prompt = "\n".join(history_lines[-6:]) + "\n" + prompt

            hermes_sid = None
            if session_id:
                save_message(session_id, "user", last_msg)
                hermes_sid = get_or_create_hermes_session(session_id)

            response = chat_with_hermes(prompt, hermes_sid)

            if session_id:
                save_message(session_id, "assistant", response)
                # Автоназва
                sess = get_session(session_id)
                if sess and sess["title"] == "Новий чат":
                    short = last_msg[:40] if last_msg else "Чат " + session_id[:4]
                    if len(short) >= 3:
                        rename_session(session_id, short)

            if stream:
                # SSE streaming
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                for chunk in response.split():
                    self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': chunk + ' '}}]})}\n\n".encode())
                    self.wfile.flush()
                self.wfile.write(f"data: {json.dumps({'choices': [{'finish_reason': 'stop'}]})}\n\n[DONE]\n".encode())
                return

            return self.json_ok({
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": response}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(prompt), "completion_tokens": len(response), "total_tokens": len(prompt) + len(response)}
            })

        # === API v1: execute ===
        if base == "/api/v1/execute":
            auth = check_auth(self.headers)
            if not auth: return self.json_error("Unauthorized", 401)
            if "exec" not in auth.get("permissions", []):
                return self.json_error("Forbidden", 403)
            cmd = data.get("command", data.get("cmd", ""))
            if not cmd: return self.json_error("Command required", 400)
            output = exec_command(cmd)
            return self.json_ok({"stdout": output, "exit_code": 0})

        # === v1: create session ===
        if base == "/api/v1/sessions":
            auth = check_auth(self.headers)
            if not auth: return self.json_error("Unauthorized", 401)
            sid = create_session(data.get("title", "API Session"))
            return self.json_ok({"session_id": sid, "title": data.get("title", "API Session")})

        # === Основні API ===

        # POST /api/sessions
        if base == "/api/sessions":
            sid = create_session(data.get("title", "Новий чат"))
            return self.json_ok({"session_id": sid, "title": data.get("title", "Новий чат")})

        # POST /api/sessions/:id/rename
        if base.startswith("/api/sessions/") and base.endswith("/rename"):
            sid = base.split("/")[3]
            rename_session(sid, data.get("title", "Чат"))
            return self.json_ok({"ok": True})

        # POST /api/sessions/:id/delete
        if base.startswith("/api/sessions/") and base.endswith("/delete"):
            sid = base.split("/")[3]
            delete_hermes_session(sid)
            delete_session(sid)
            return self.json_ok({"ok": True})

        # POST /api/chat
        if base == "/api/chat":
            message = data.get("message", "")
            session_id = data.get("session_id", "")
            history = data.get("history", [])
            media = data.get("media")

            if not message and not media:
                return self.json_error("Message required", 400)

            full_message = message
            if media:
                full_message = f"{message}\n[📎 {media['type']}: {media['name']}]" if message else f"[📎 {media['type']}: {media['name']}]"

            if session_id:
                save_message(session_id, "user", message, media)

            hermes_sid = None
            if session_id:
                hermes_sid = get_or_create_hermes_session(session_id)

            history_text = ""
            if history:
                lines = []
                for h in history[-10:]:
                    role = "Користувач" if h.get("role") == "user" else "Hermes"
                    lines.append(f"{role}: {h.get('text', '')}")
                history_text = "\n".join(lines)

            response = chat_with_hermes(full_message, hermes_sid, history_text)

            if session_id:
                save_message(session_id, "assistant", response)
                sess = get_session(session_id)
                if sess and sess["title"] == "Новий чат":
                    short = message[:40] if message else "Медіа"
                    if len(short) >= 3:
                        rename_session(session_id, short)

            return self.json_ok({"response": response})

        # POST /api/exec
        if base == "/api/exec":
            cmd = data.get("cmd", "")
            if not cmd: return self.json_error("Command required", 400)
            output = exec_command(cmd)
            return self.json_ok({"output": output})

        self.json_error("Not found", 404)

    # ====== DELETE ======
    def do_DELETE(self):
        base, _ = route(self.path)
        if base.startswith("/api/sessions/"):
            sid = base.split("/")[3]
            delete_hermes_session(sid)
            delete_session(sid)
            return self.json_ok({"ok": True})
        if base.startswith("/api/v1/sessions/"):
            auth = check_auth(self.headers)
            if not auth: return self.json_error("Unauthorized", 401)
            sid = base.split("/")[4]
            delete_hermes_session(sid)
            delete_session(sid)
            return self.json_ok({"ok": True})
        self.json_error("Not found", 404)

    # ====== УТИЛІТИ ======

    def json_ok(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def json_error(self, msg, status=400):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8"))

    def serve_file(self, path, mime):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return self.json_error("Not found", 404)
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(path, "rb") as f:
            self.wfile.write(f.read())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
        self.end_headers()

    def log_message(self, fmt, *args):
        if "/api/" in str(args):
            print(f"[API] {self.command} {args[0]} {args[1]}")

# ====== ЗАПУСК ======

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

if __name__ == "__main__":
    get_db()
    ip = get_local_ip()

    print(f"""
╔══════════════════════════════════════════╗
║  🤖 Hermonoid Chat + API Server         ║
╠══════════════════════════════════════════╣
║  📱 http://localhost:{PORT}              ║
║  📡 http://{ip}:{PORT}                   ║
╠══════════════════════════════════════════╣
║  Веб-чат:    /                           ║
║  Сесії:      GET/POST /api/sessions      ║
║  Чат:        POST   /api/chat            ║
║  Команди:    POST   /api/exec            ║
║  ──────────────────────────────────────── ║
║  REST API v1 (OpenAI-сумісний):          ║
║  Моделі:     GET    /api/v1/models       ║
║  Чат:        POST   /api/v1/chat/completions ║
║  Команди:    POST   /api/v1/execute      ║
║  Сесії:      GET    /api/v1/sessions     ║
╠══════════════════════════════════════════╣
║  API ключ:  Authorization: Bearer <key>  ║
║             або X-API-Key: <key>         ║
║  Ключі в:   ~/hermonoid/config/api_keys.json ║
╚══════════════════════════════════════════╝
""")

    server = http.server.HTTPServer((HOST, PORT), ChatHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹ Зупинено.")
        server.server_close()
