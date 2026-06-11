"""Hermonoid v4 — mobile AI agent with Hermes-style tools + Termux bootstrap."""

import json, os, sqlite3, threading, time, uuid, re, subprocess, sys, logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[Hermonoid] %(message)s")
log = logging.getLogger("hermonoid")

PORT, HOST = 8080, "127.0.0.1"

def _get_paths():
    """Get data paths — can be overridden for testing via env vars."""
    if "HERMONOID_DB_DIR" in os.environ:
        db_dir = os.environ["HERMONOID_DB_DIR"]
        assets_dir = os.environ.get("HERMONOID_ASSETS_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
    else:
        db_dir = "/data/data/com.hermonoid.app/files"
        assets_dir = db_dir + "/chaquopy/asset"
    return {
        "db_dir": db_dir,
        "assets_dir": assets_dir,
        "db_path": os.path.join(db_dir, "hermonoid.db"),
        "config_path": os.path.join(db_dir, "config.json"),
        "termux_home": os.path.join(db_dir, "termux-home"),
        "termux_prefix": os.path.join(db_dir, "termux-prefix"),
    }

PATHS = _get_paths()

# ── Default config ──
DEFAULT_CONFIG = {
    "provider": "gonka",
    "model": "deepseek/deepseek-v4-flash",
    "api_key": "",
    "base_url": "https://proxy.gonka.gg/v1",
    "system_prompt": (
        "Ти — Hermes Agent на мобільному. "
        "Відповідай українською. Маєш повноцінний Termux: запускай bash-команди, "
        "читай/пиши файли, встановлюй пакети через pkg/apt, виконуй Python скрипти. "
        "Використовуй execute_command для всього, що робив би в терміналі."
    ),
    "max_tokens": 4096,
    "temperature": 0.7,
}

# ── Available models ──
AVAILABLE_MODELS = [
    {"id": "deepseek/deepseek-v4-flash", "name": "DeepSeek V4 Flash", "provider": "DeepSeek"},
    {"id": "qwen/Qwen3-235B-A22B-Instruct-2507-FP8", "name": "Qwen3 235B", "provider": "Gonka"},
    {"id": "moonshotai/Kimi-K2.6", "name": "Kimi K2.6", "provider": "Gonka"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenRouter"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
]

# ── Config ──
def load_config():
    if os.path.exists(PATHS["config_path"]):
        try:
            with open(PATHS["config_path"]) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    os.makedirs(PATHS["db_dir"], exist_ok=True)
    existing = load_config()
    existing.update(cfg)
    with open(PATHS["config_path"], "w") as f:
        json.dump(existing, f, indent=2)

# ── Database ──
_db_local = threading.local()

def get_db():
    if not hasattr(_db_local, "conn") or _db_local.conn is None:
        conn = sqlite3.connect(PATHS["db_path"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, title TEXT NOT NULL,
            created_at REAL, updated_at REAL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL, role TEXT NOT NULL,
            text TEXT DEFAULT '', created_at REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )""")
        conn.commit()
        _db_local.conn = conn
    return _db_local.conn

def close_db():
    if hasattr(_db_local, "conn") and _db_local.conn:
        _db_local.conn.close()
        _db_local.conn = None

def create_session(title="Новий чат"):
    sid = uuid.uuid4().hex[:8]; now = time.time()
    conn = get_db()
    conn.execute("INSERT INTO sessions(id,title,created_at,updated_at) VALUES(?,?,?,?)", (sid,title,now,now))
    conn.commit(); return sid

def list_sessions():
    conn = get_db()
    rows = conn.execute("SELECT id,title,created_at,updated_at,(SELECT COUNT(*) FROM messages WHERE session_id=id) as msg_count FROM sessions ORDER BY updated_at DESC LIMIT 50").fetchall()
    return [dict(r) for r in rows]

def get_session(sid):
    conn = get_db()
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    return dict(row) if row else None

def rename_session(sid, title):
    conn = get_db()
    conn.execute("UPDATE sessions SET title=?,updated_at=? WHERE id=?", (title, time.time(), sid))
    conn.commit()

def delete_session(sid):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
    conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    conn.commit()

def save_message(sid, role, text):
    conn = get_db()
    conn.execute("INSERT INTO messages(session_id,role,text,created_at) VALUES(?,?,?,?)", (sid,role,text,time.time()))
    conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (time.time(), sid))
    conn.commit()

def get_messages(sid, limit=50):
    conn = get_db()
    rows = conn.execute("SELECT role,text,created_at FROM messages WHERE session_id=? ORDER BY created_at ASC LIMIT ?", (sid, limit)).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in rows]


# ── Termux Bridge ──
def setup_termux():
    """Verify Termux bootstrap was extracted by Java (fast check)."""
    prefix = PATHS["termux_prefix"]
    marker = os.path.join(prefix, ".setup_done")
    
    if os.path.exists(marker):
        log.info("Termux bootstrap ready at " + prefix)
        return True
    
    # Java should have done the extraction. If marker not found,
    # it's still in progress or failed.
    log.warning("Termux marker not found — Java extraction may still be in progress")
    return False

def get_termux_env():
    """Get environment variables for running Termux commands."""
    prefix = PATHS["termux_prefix"]
    home = PATHS["termux_home"]
    return {
        "HOME": home,
        "PREFIX": prefix,
        "PATH": f"{prefix}/bin:{prefix}/bin/applets:/system/bin:/system/xbin",
        "LD_LIBRARY_PATH": f"{prefix}/lib",
        "TMPDIR": "/data/local/tmp",
        "TERMUX_VERSION": "0.118.3",
        "TERMUX_APK_RELEASE": "F-Droid",
    }

def exec_command(cmd, timeout=30):
    """Execute a shell command in Termux environment using Termux's own shell."""
    prefix = PATHS["termux_prefix"]
    home = PATHS["termux_home"]
    
    env = os.environ.copy()
    env.update(get_termux_env())
    
    # Use Termux's bash directly if available
    bash_path = f"{prefix}/bin/bash"
    if not os.path.exists(bash_path):
        bash_path = "/system/bin/sh"
    
    try:
        result = subprocess.run(
            [bash_path, "-c", cmd],
            env=env, capture_output=True, text=True,
            timeout=timeout, cwd=home,
        )
        output = result.stdout or ""
        if result.stderr:
            # Filter out common noise
            stderr_lines = [l for l in result.stderr.split("\n") 
                          if l.strip() and "WARNING" not in l and "skipping" not in l.lower()]
            if stderr_lines:
                output += "\n[STDERR]\n" + "\n".join(stderr_lines)
        return output[:6000] if output else "(команда виконана, виводу немає)"
    except subprocess.TimeoutExpired:
        return f"⏱ Команда перевищила ліміт {timeout}с"
    except subprocess.CalledProcessError as e:
        return f"❌ Помилка (код {e.returncode}): {e.stderr[:500] or e.stdout[:500]}"
    except Exception as e:
        return f"❌ Помилка виконання: {e}"

def exec_python(code, timeout=15):
    """Execute Python code using Termux's python3 if available, else Chaquopy's Python."""
    prefix = PATHS["termux_prefix"]
    python3 = f"{prefix}/bin/python3"
    
    if os.path.exists(python3):
        env = os.environ.copy()
        env.update(get_termux_env())
        try:
            result = subprocess.run(
                [python3, "-c", code],
                env=env, capture_output=True, text=True,
                timeout=timeout,
            )
            output = result.stdout or ""
            if result.stderr:
                stderr = result.stderr.strip()
                if stderr:
                    output += "\n[STDERR]\n" + stderr
            return output[:3000] if output else "✅ Виконано"
        except subprocess.TimeoutExpired:
            return "⏱ Python перевищив ліміт 15с"
        except Exception as e:
            return f"❌ {e}"
    
    # Fallback: use Chaquopy's Python
    import io
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        exec(code, {"__builtins__": __builtins__})
        output = buf.getvalue()
        return output[:2000] if output else "✅ Виконано"
    except Exception as e:
        return f"❌ {e}"
    finally:
        sys.stdout = old_stdout

def read_termux_file(path):
    """Read a file from Termux filesystem."""
    full = os.path.join(PATHS["termux_home"], path.lstrip("/"))
    if not os.path.exists(full):
        # Also try from prefix
        full2 = os.path.join(PATHS["termux_prefix"], path.lstrip("/"))
        if os.path.exists(full2):
            full = full2
        else:
            return f"❌ Файл не знайдено: {path}"
    try:
        with open(full, "r", errors="replace") as f:
            content = f.read()
        return content[:6000]
    except Exception as e:
        return f"❌ Помилка читання: {e}"

def write_termux_file(path, content):
    """Write a file to Termux home directory."""
    full = os.path.join(PATHS["termux_home"], path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    try:
        with open(full, "w") as f:
            f.write(content)
        return f"✅ Записано {len(content)} байт у {path}"
    except Exception as e:
        return f"❌ Помилка запису: {e}"


# ── AI Agent Tools ──
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a bash/shell command in Termux (apt, pkg, python, node, curl, git, tar, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (max 120)", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Execute Python code and get result",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_termux_file",
            "description": "Read a file from Termux home or prefix directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to Termux home"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_termux_file",
            "description": "Write content to a file in Termux home",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to Termux home"},
                    "content": {"type": "string", "description": "File content"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get current date and time",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]

TOOL_MAP = {
    "execute_command": lambda c, t=30: exec_command(c, t),
    "execute_python": lambda code: exec_python(code),
    "read_termux_file": lambda path: read_termux_file(path),
    "write_termux_file": lambda path, content: write_termux_file(path, content),
    "search_web": lambda query: _web_search(query),
    "get_time": lambda: f"🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}",
}

def _web_search(query):
    import urllib.request, urllib.parse, html
    try:
        url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
        with urllib.request.urlopen(url, timeout=10) as r:
            text = html.unescape(re.sub(r'<[^>]+>', ' ', r.read().decode('utf-8')))
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 30]
            return '\n'.join(lines[:8])[:2000]
    except Exception as e:
        return f"❌ {e}"


# ── AI Agent Loop (Hermes-style) ──
def agent_chat(messages, config, max_turns=8):
    """Multi-turn agent with tool calling (Hermes Agent pattern)."""
    api_key = config.get("api_key", "")
    if not api_key:
        return "❌ API ключ не налаштовано. Відкрий Налаштування."

    model = config.get("model", DEFAULT_CONFIG["model"])
    base_url = config.get("base_url", DEFAULT_CONFIG["base_url"])
    max_tokens = config.get("max_tokens", 4096)
    temperature = config.get("temperature", 0.7)
    system_prompt = config.get("system_prompt", DEFAULT_CONFIG["system_prompt"])

    import requests as req

    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    msgs = [{"role": "system", "content": system_prompt}]
    msgs.extend(messages[-20:])

    for turn in range(max_turns):
        payload = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "tools": TOOLS,
            "tool_choice": "auto",
        }

        try:
            resp = req.post(url, headers=headers, json=payload, timeout=120)
        except Exception as e:
            return f"❌ Мережева помилка: {e}"

        if resp.status_code == 401:
            return "❌ Невірний API ключ"
        elif resp.status_code == 402:
            return "❌ Недостатньо коштів на рахунку"
        elif resp.status_code == 429:
            return "❌ Ліміт запитів. Зачекай."
        elif resp.status_code != 200:
            return f"❌ Помилка API ({resp.status_code})"

        try:
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls", [])
        except Exception as e:
            return f"❌ Помилка парсингу: {e}"

        # Add assistant response to message chain
        if tool_calls:
            msgs.append({"role": "assistant", "content": content or None, "tool_calls": tool_calls})
        else:
            msgs.append({"role": "assistant", "content": content})
            # Extract reasoning if present
            reasoning = msg.get("reasoning_content", "")
            if reasoning:
                return f"<details><summary>🧠 Роздуми</summary>{reasoning}</details>\n\n{content}"
            return content or "🤖 ..."

        # Execute tools
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args_str = fn.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except:
                args = {}

            tool_fn = TOOL_MAP.get(name)
            if tool_fn:
                try:
                    result = tool_fn(**args)
                except Exception as e:
                    result = f"❌ Помилка {name}: {e}"
            else:
                result = f"❌ Невідомий інструмент: {name}"

            msgs.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": str(result)})

    return "⏱ Досягнуто максимум кроків агента"


# ── HTTP Handler ──
class Handler(BaseHTTPRequestHandler):
    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_static(self, path):
        for prefix in ["web/", ""]:
            full = os.path.join(PATHS["assets_dir"], prefix, path.lstrip("/"))
            if os.path.isfile(full):
                ext = os.path.splitext(full)[1].lower()
                mime = {
                    ".html": "text/html; charset=utf-8", ".css": "text/css",
                    ".js": "application/javascript", ".png": "image/png",
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".svg": "image/svg+xml", ".ico": "image/x-icon",
                    ".json": "application/json", ".webp": "image/webp",
                }.get(ext, "application/octet-stream")
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(full, "rb") as f:
                    self.wfile.write(f.read())
                return
        self._json({"error": "Not found"}, 404)

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        # Static files
        if path in ("", "/", "/index.html"):
            return self._serve_static("index.html")
        if path in ("/settings.html", "/settings"):
            return self._serve_static("settings.html")

        # API endpoints
        if path == "/api/status":
            termux_marker = os.path.join(PATHS["termux_prefix"], ".setup_done")
            bash_path = os.path.join(PATHS["termux_prefix"], "bin", "bash")
            return self._json({
                "status": "ok", "version": "4.0.0",
                "app": "Hermonoid",
                "termux_ready": os.path.exists(termux_marker) and os.path.exists(bash_path),
                "python_version": sys.version.split()[0],
            })

        if path == "/api/sessions":
            return self._json({"sessions": list_sessions()})

        if path == "/api/config":
            cfg = load_config()
            return self._json({
                "key_set": bool(cfg.get("api_key")),
                "model": cfg.get("model"),
                "base_url": cfg.get("base_url"),
                "system_prompt": cfg.get("system_prompt"),
                "temperature": cfg.get("temperature"),
                "max_tokens": cfg.get("max_tokens"),
                "models": AVAILABLE_MODELS,
            })

        if path == "/api/models":
            return self._json({"models": AVAILABLE_MODELS})

        if path.startswith("/api/sessions/"):
            parts = path.split("/")
            if len(parts) == 4:
                s = get_session(parts[3])
                if s:
                    return self._json({"session": s, "messages": get_messages(parts[3])})
                return self._json({"error": "Not found"}, 404)

        self._json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        data = self._read_body()

        if path == "/api/chat":
            message = data.get("message", "")
            session_id = data.get("session_id", "")
            history = data.get("history", [])
            if not message:
                return self._json({"error": "Message required"}, 400)
            if session_id:
                save_message(session_id, "user", message)
            cfg = load_config()
            msgs = [{"role": "user" if h.get("role")=="user" else "assistant", "content": h.get("text","")} for h in history[-20:]]
            msgs.append({"role": "user", "content": message})
            response = agent_chat(msgs, cfg)
            if session_id:
                save_message(session_id, "assistant", response)
                s = get_session(session_id)
                if s and s["title"] == "Новий чат" and len(message) >= 3:
                    rename_session(session_id, message[:40])
            return self._json({"response": response})

        if path == "/api/sessions":
            sid = create_session(data.get("title", "Новий чат"))
            return self._json({"session_id": sid})

        if path.startswith("/api/sessions/") and path.endswith("/rename"):
            rename_session(path.split("/")[3], data.get("title", "Чат"))
            return self._json({"ok": True})

        if path.startswith("/api/sessions/") and path.endswith("/delete"):
            delete_session(path.split("/")[3])
            return self._json({"ok": True})

        if path == "/api/settings":
            cfg = load_config()
            for k in ("api_key", "model", "base_url", "system_prompt", "temperature", "max_tokens"):
                if k in data:
                    cfg[k] = data[k]
            save_config(cfg)
            return self._json({"ok": True, "key_set": bool(cfg.get("api_key"))})

        self._json({"error": "Not found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path.rstrip("/")
        if path.startswith("/api/sessions/"):
            delete_session(path.split("/")[3])
            return self._json({"ok": True})
        self._json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.end_headers()

    def log_message(self, fmt, *args):
        if "/api/" in str(args):
            log.info(f"{self.command} {args[0]}")


# ── Server lifecycle ──
_server = None

def start_server(assets_path=None, db_dir=None):
    global _server, PATHS
    if assets_path:
        PATHS["assets_dir"] = assets_path
    if db_dir:
        PATHS["db_dir"] = db_dir
        PATHS["db_path"] = os.path.join(db_dir, "hermonoid.db")
        PATHS["config_path"] = os.path.join(db_dir, "config.json")
        PATHS["termux_home"] = os.path.join(db_dir, "termux-home")
        PATHS["termux_prefix"] = os.path.join(db_dir, "termux-prefix")

    os.makedirs(PATHS["db_dir"], exist_ok=True)
    get_db()
    setup_termux()

    _server = HTTPServer((HOST, PORT), Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    log.info(f"Hermonoid v4 running on {HOST}:{PORT}")
    return PORT

def stop_server():
    global _server
    if _server:
        _server.shutdown()
        _server = None
        close_db()
        log.info("Server stopped")


if __name__ == "__main__":
    db_dir = os.environ.get("HERMONOID_DB_DIR", "/tmp/hermonoid-test")
    assets_dir = os.environ.get("HERMONOID_ASSETS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
    port = start_server(assets_dir, db_dir)
    print(f"Hermonoid test: http://{HOST}:{port}")
    print(f"DB: {PATHS['db_path']}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_server()
