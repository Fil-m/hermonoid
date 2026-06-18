"""Hermonoid — Flask сервер для графічного інтерфейсу Hermes Agent.
Запуск: python server.py
Відкрити: http://localhost:8550
"""

import os
import sys
import json
import threading
import base64
import subprocess
import re
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

from hermes_api import (
    _hermes_bin,
    load_config, save_config, load_env, save_env,
    query_hermes, doctor_check, get_status,
    get_providers, get_models_for_provider, get_env_keys,
    get_personalities, get_available_skins, list_profiles,
    create_profile, delete_profile,
)

HERE = Path(__file__).parent
STATIC_DIR = HERE / "static"
TEMPLATE_DIR = HERE / "templates"

app = Flask(__name__, 
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATE_DIR),
)

STATIC_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)


@app.route("/")
def index():
    return send_from_directory(str(HERE), "index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Порожнє повідомлення"}), 400
    response = query_hermes(message)
    return jsonify({"response": response})


@app.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify(load_config())


@app.route("/api/config", methods=["POST"])
def api_save_config():
    data = request.get_json() or {}
    return jsonify({"status": save_config(data)})


@app.route("/api/env", methods=["GET"])
def api_get_env():
    return jsonify(load_env())


@app.route("/api/env", methods=["POST"])
def api_save_env():
    data = request.get_json() or {}
    return jsonify({"status": save_env(data)})


@app.route("/api/env/keys", methods=["GET"])
def api_get_env_keys():
    keys = get_env_keys()
    return jsonify([{"key": k, "label": l} for k, l in keys])


@app.route("/api/providers", methods=["GET"])
def api_get_providers():
    providers = get_providers()
    result = {}
    for p in providers:
        result[p] = get_models_for_provider(p)
    return jsonify(result)


@app.route("/api/personalities", methods=["GET"])
def api_get_personalities():
    return jsonify(get_personalities())


@app.route("/api/skins", methods=["GET"])
def api_get_skins():
    return jsonify(get_available_skins())


@app.route("/api/profiles", methods=["GET"])
def api_get_profiles():
    return jsonify(list_profiles())


@app.route("/api/profiles", methods=["POST"])
def api_create_profile():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    return jsonify({"status": create_profile(name)})


@app.route("/api/profiles/delete", methods=["POST"])
def api_delete_profile():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    return jsonify({"status": delete_profile(name)})


@app.route("/api/doctor", methods=["GET"])
def api_doctor():
    return jsonify({"issues": doctor_check()})


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(get_status())


@app.route("/api/toolsets", methods=["GET"])
def api_get_toolsets():
    all_tools = [
        "web", "search", "browser", "terminal", "file", "code_execution",
        "vision", "image_gen", "video", "tts", "skills", "memory",
        "session_search", "delegation", "cronjob", "clarify", "messaging",
        "todo", "kanban", "debugging", "safe", "spotify", "homeassistant",
        "discord", "discord_admin", "feishu_doc", "feishu_drive",
        "yuanbao", "rl", "moa"
    ]
    return jsonify(all_tools)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    data = request.get_json() or {}
    filename = data.get("filename", "file")
    content = data.get("content", "")
    filetype = data.get("type", "text")
    try:
        raw = base64.b64decode(content)
        tmpdir = HERE / "uploads"
        tmpdir.mkdir(exist_ok=True)
        fpath = tmpdir / filename
        with open(fpath, "wb") as f:
            f.write(raw)
        if filetype == "text":
            try:
                text = raw.decode("utf-8", errors="replace")
                return jsonify({"status": "ok", "path": str(fpath), "preview": text[:2000]})
            except:
                pass
        return jsonify({"status": "ok", "path": str(fpath), "size": len(raw)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/file/<path:filename>")
def api_get_file(filename):
    return send_from_directory(str(HERE / "uploads"), filename)


@app.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """List recent Hermes sessions via JSONL export."""
    try:
        bin_path = _hermes_bin()
        result = subprocess.run(
            [bin_path, "sessions", "export", "-"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0 or not result.stdout.strip():
            return jsonify([])
        
        sessions = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                s = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            sid = s.get("id", "")
            if not sid:
                continue
            
            # Extract first user message from messages array
            first_msg = ""
            messages = s.get("messages", [])
            if messages:
                for m in messages:
                    if m.get("role") == "user" and m.get("content"):
                        first_msg = m["content"][:120]
                        break
            
            title = s.get("title") or first_msg or ""
            started = s.get("started_at", 0)
            ended = s.get("ended_at", 0)
            
            sessions.append({
                "id": sid,
                "title": title[:80],
                "started_at": int(started) if isinstance(started, (int, float)) and started else None,
                "ended_at": int(ended) if isinstance(ended, (int, float)) and ended else None,
                "message_count": s.get("message_count", 0),
                "input_tokens": s.get("input_tokens", 0),
                "output_tokens": s.get("output_tokens", 0),
                "source": s.get("source", "cli"),
                "first_user_msg": first_msg,
                "last_active": s.get("last_active", started),
            })
        
        sessions.sort(key=lambda x: x.get("last_active") or 0, reverse=True)
        return jsonify(sessions[:100])
    except Exception as e:
        return jsonify({"error": str(e), "sessions": []})


@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def api_session_messages(session_id):
    """Get messages for a specific session."""
    limit = request.args.get("limit", 200, type=int)
    try:
        bin_path = _hermes_bin()
        result = subprocess.run(
            [bin_path, "sessions", "export", "-"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0 or not result.stdout.strip():
            return jsonify([])
        
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                s = json.loads(line)
            except json.JSONDecodeError:
                continue
            if s.get("id") == session_id:
                raw_messages = s.get("messages", [])
                
                # Filter to user/assistant messages (skip tool calls/results)
                filtered = []
                for m in raw_messages:
                    role = m.get("role", "")
                    if role == "user":
                        filtered.append({
                            "role": "user",
                            "content": m.get("content", "") or "",
                            "timestamp": m.get("timestamp", 0),
                        })
                    elif role == "assistant":
                        # Get assistant text content (skip tool call blocks)
                        content = m.get("content", "") or ""
                        tool_calls = m.get("tool_calls") or []
                        if not content and tool_calls:
                            content = f"[Виклик інструменту: {tool_calls[0].get('function', {}).get('name', '?')}]"
                        filtered.append({
                            "role": "assistant",
                            "content": content,
                            "timestamp": m.get("timestamp", 0),
                        })
                
                filtered = filtered[:limit]
                return jsonify(filtered)
        
        return jsonify({"error": "Session not found", "messages": []}), 404
    except Exception as e:
        return jsonify({"error": str(e), "messages": []}), 500


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    try:
        result = subprocess.run(
            [_hermes_bin(), "sessions", "delete", session_id],
            capture_output=True, text=True, timeout=10
        )
        return jsonify({"status": "✅ Сесію видалено"})
    except Exception as e:
        return jsonify({"status": f"❌ {e}"}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8550))
    debug = "--debug" in sys.argv
    
    print(f"╔══════════════════════════════════╗")
    print(f"║    Hermonoid GUI для Hermes Agent   ║")
    print(f"╠══════════════════════════════════╣")
    print(f"║  Відкрийте в браузері:           ║")
    print(f"║  http://localhost:{port}             ║")
    print(f"║                                  ║")
    print(f"║  Для зупинки: Ctrl+C             ║")
    print(f"╚══════════════════════════════════╝")
    
    app.run(host="0.0.0.0", port=port, debug=debug)
