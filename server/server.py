#!/data/data/com.termux/files/home/.venv/bin/python
"""
Hermes Chat Server — веб-чат з Hermes Agent через браузер
З сесіями, збереженням історії та перемиканням між чатами
"""

import http.server
import json
import os
import socket
import subprocess
import sqlite3
import uuid
import time
import threading
import re

PORT = 8080
HOST = "0.0.0.0"
HERMES_BIN = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
DB_PATH = os.path.expanduser("~/hermes_chat/sessions.db")

# ====== SQLite Сховище ======

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            media TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hermes_sessions (
            web_session_id TEXT PRIMARY KEY,
            hermes_session_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (web_session_id) REFERENCES sessions(id)
        )
    """)
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
        (sid, role, text, json.dumps(media) if media else None, time.time())
    )
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (time.time(), sid))
    conn.commit()
    conn.close()

def get_messages(sid, limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT role, text, media, created_at FROM messages "
        "WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
        (sid, limit)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        msg = {"role": r["role"], "text": r["text"]}
        if r["media"]:
            msg["media"] = json.loads(r["media"])
        result.append(msg)
    return result

def get_or_create_hermes_session(web_sid):
    """Отримати Hermes session_id для веб-сесії, або створити нову"""
    conn = get_db()
    row = conn.execute(
        "SELECT hermes_session_id FROM hermes_sessions WHERE web_session_id = ?",
        (web_sid,)
    ).fetchone()
    if row:
        conn.close()
        return row["hermes_session_id"]

    # Створюємо нову Hermes сесію
    hermes_sid = str(uuid.uuid4())[:12]
    conn.execute(
        "INSERT INTO hermes_sessions (web_session_id, hermes_session_id, created_at) VALUES (?, ?, ?)",
        (web_sid, hermes_sid, time.time())
    )
    conn.commit()
    conn.close()
    return hermes_sid

def delete_hermes_session(web_sid):
    conn = get_db()
    conn.execute("DELETE FROM hermes_sessions WHERE web_session_id = ?", (web_sid,))
    conn.commit()
    conn.close()

# ====== Hermes інтеграція ======

def chat_with_hermes(message, hermes_session_id=None, history_text=None):
    """Надіслати повідомлення Hermes через CLI з контекстом"""
    try:
        # Будуємо повний промпт з історією
        prompt = message
        if history_text and hermes_session_id:
            # Використовуємо --continue для продовження сесії
            cmd = [HERMES_BIN, "chat", "-q", prompt, "--quiet"]
            if hermes_session_id:
                cmd.extend(["--resume", hermes_session_id])
        else:
            cmd = [HERMES_BIN, "chat", "-q", prompt, "--quiet"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "TERM": "xterm-256color"}
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        elif result.stderr.strip():
            return f"⚠️ {result.stderr.strip()}"
        else:
            return "❌ Немає відповіді від Hermes"
    except subprocess.TimeoutExpired:
        return "⏱ Час вичерпано (180s)"
    except FileNotFoundError:
        return f"❌ Hermes не знайдено"
    except Exception as e:
        return f"❌ Помилка: {str(e)}"

def exec_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if not output.strip():
            output = f"✅ Команда виконана (exit code: {result.returncode})"
        return output.strip()
    except subprocess.TimeoutExpired:
        return "⏱ Timeout"
    except Exception as e:
        return f"❌ {str(e)}"

# ====== Сервер ======

class ChatHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            with open(html_path, "rb") as f:
                self.wfile.write(f.read())

        elif self.path == "/api/status":
            self.send_json({"status": "ok", "sessions": len(list_sessions())})

        elif self.path == "/api/sessions":
            self.send_json({"sessions": list_sessions()})

        elif self.path.startswith("/api/sessions/"):
            parts = self.path.split("/")
            if len(parts) == 4:
                sid = parts[3]
                session = get_session(sid)
                if session:
                    messages = get_messages(sid)
                    self.send_json({"session": session, "messages": messages})
                else:
                    self.send_json({"error": "Session not found"}, 404)
            elif len(parts) == 5 and parts[4] == "messages":
                sid = parts[3]
                messages = get_messages(sid)
                self.send_json({"messages": messages})
            else:
                self.send_json({"error": "Not found"}, 404)

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        path = self.path

        if path == "/api/sessions":
            # Створити нову сесію
            data = json.loads(body) if content_length else {}
            title = data.get("title", "Новий чат")
            sid = create_session(title)
            self.send_json({"session_id": sid, "title": title})

        elif path.startswith("/api/sessions/") and path.endswith("/rename"):
            sid = path.split("/")[3]
            data = json.loads(body)
            title = data.get("title", "Чат")
            rename_session(sid, title)
            self.send_json({"ok": True})

        elif path.startswith("/api/sessions/") and path.endswith("/delete"):
            sid = path.split("/")[3]
            delete_hermes_session(sid)
            delete_session(sid)
            self.send_json({"ok": True})

        elif path == "/api/chat":
            try:
                data = json.loads(body)
                message = data.get("message", "")
                session_id = data.get("session_id", "")
                history = data.get("history", [])

                if not message and not data.get("media"):
                    self.send_json({"error": "Message is required"}, 400)
                    return

                # Якщо є медіа — додаємо інфо про нього в повідомлення
                full_message = message
                media = data.get("media")
                if media:
                    media_info = f"\n[📎 {media['type']}: {media['name']}]"
                    full_message = message + media_info if message else media_info

                # Зберігаємо повідомлення користувача
                if session_id:
                    save_message(session_id, "user", message, media)

                # Отримуємо або створюємо Hermes сесію
                hermes_sid = None
                if session_id:
                    hermes_sid = get_or_create_hermes_session(session_id)

                # Формуємо історію для контексту
                history_text = ""
                if history:
                    lines = []
                    for h in history[-10:]:
                        role = "Користувач" if h["role"] == "user" else "Hermes"
                        lines.append(f"{role}: {h['text']}")
                    history_text = "\n".join(lines)

                # Відповідь Hermes
                response = chat_with_hermes(full_message, hermes_sid, history_text)

                # Зберігаємо відповідь
                if session_id:
                    save_message(session_id, "assistant", response)

                # Автоназва сесії за першим повідомленням
                if session_id:
                    session = get_session(session_id)
                    if session and session["title"] == "Новий чат":
                        short_title = message[:40] if message else "Медіа"
                        if len(short_title) < 3:
                            short_title = "Чат " + session_id[:4]
                        rename_session(session_id, short_title)

                self.send_json({"response": response})

            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif path == "/api/exec":
            try:
                data = json.loads(body)
                cmd = data.get("cmd", "")
                output = exec_command(cmd)
                self.send_json({"output": output})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        if self.path.startswith("/api/sessions/"):
            sid = self.path.split("/")[3]
            delete_hermes_session(sid)
            delete_session(sid)
            self.send_json({"ok": True})
        else:
            self.send_json({"error": "Not found"}, 404)

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        if "/api/" in str(args):
            print(f"[API] {args[0]} {args[1]}")

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
    # Ініціалізація БД
    get_db()
    ip = get_local_ip()

    print("\n" + "="*50)
    print("  🤖 Hermes Chat Server v2 — з сесіями")
    print("="*50)
    print(f"\n  📱 Локально:  http://localhost:{PORT}")
    print(f"  📡 Мережа:    http://{ip}:{PORT}")
    print(f"\n  ✅ Сесії зберігаються в SQLite")
    print(f"  🔧 API:")
    print(f"     GET  /api/sessions          — список сесій")
    print(f"     POST /api/sessions          — створити сесію")
    print(f"     GET  /api/sessions/:id      — сесія + повідомлення")
    print(f"     POST /api/sessions/:id/rename — перейменувати")
    print(f"     DELETE /api/sessions/:id    — видалити")
    print(f"     POST /api/chat              — спілкування")
    print(f"     POST /api/exec              — команди")
    print(f"\n  Натисни Ctrl+C для зупинки\n")
    print("="*50 + "\n")

    server = http.server.HTTPServer((HOST, PORT), ChatHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  ⏹ Зупинено.")
        server.server_close()
