"""Hermes Agent API wrapper — communicates with Hermes CLI and reads/writes config."""

import subprocess
import os
import yaml
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
CONFIG_PATH = HERMES_HOME / "config.yaml"
ENV_PATH = HERMES_HOME / ".env"
HERMES_BIN = HERMES_HOME / "hermes-agent" / "venv" / "bin" / "hermes"


def _hermes_bin():
    if HERMES_BIN.exists():
        return str(HERMES_BIN)
    return "hermes"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(cfg: dict) -> str:
    try:
        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return "✅ Налаштування збережено"
    except Exception as e:
        return f"❌ Помилка: {e}"


def load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("\"'")
    return env


def save_env(env: dict) -> str:
    try:
        lines = []
        for k, v in sorted(env.items()):
            if v:
                lines.append(f'{k}="{v}"')
        with open(ENV_PATH, "w") as f:
            f.write("\n".join(lines) + "\n")
        return "✅ API ключі збережено"
    except Exception as e:
        return f"❌ Помилка: {e}"


def query_hermes(query: str, timeout: int = 180) -> str:
    """Send a query to Hermes and return response."""
    try:
        result = subprocess.run(
            [_hermes_bin(), "chat", "-q", query, "-Q"],
            capture_output=True, text=True, timeout=timeout
        )
        out = result.stdout + "\n" + result.stderr
        return out.strip()
    except subprocess.TimeoutExpired:
        return "⏱️ Таймаут. Hermes не встиг відповісти за 180 секунд."
    except Exception as e:
        return f"❌ Помилка: {e}"


def doctor_check() -> list:
    try:
        result = subprocess.run(
            [_hermes_bin(), "doctor"],
            capture_output=True, text=True, timeout=30
        )
        out = result.stdout + result.stderr
        lines = out.split("\n")
        issues = [l.strip() for l in lines if l.strip() and ("✗" in l or "❌" in l or "fail" in l.lower() or "error" in l.lower())]
        return issues or ["✅ Все добре"]
    except Exception as e:
        return [f"❌ Помилка: {e}"]


def get_status() -> dict:
    info = {"model": "невідомо", "provider": "невідомо", "version": "невідомо"}
    try:
        r = subprocess.run([_hermes_bin(), "--version"], capture_output=True, text=True, timeout=10)
        info["version"] = (r.stdout.strip() or r.stderr.strip()).split("\n")[0]
    except:
        pass
    return info


def get_providers() -> list:
    return [
        "openrouter", "anthropic", "openai", "deepseek", "google",
        "xai", "huggingface", "nous", "github", "mistral", "cohere",
        "together", "groq", "fireworks", "perplexity", "replicate",
        "zai", "minimax", "kimi", "alibaba", "xiaomi", "custom"
    ]


def get_models_for_provider(provider: str) -> list:
    MODELS = {
        "openrouter": ["auto"],
        "anthropic": ["claude-sonnet-4", "claude-3.5-haiku", "claude-3-opus"],
        "openai": ["gpt-4o", "gpt-4o-mini", "o3-mini", "gpt-4.1"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "google": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        "xai": ["grok-3", "grok-4.20-reasoning", "grok-4-vision"],
        "huggingface": ["auto"],
        "nous": ["auto"],
        "github": ["copilot"],
        "mistral": ["mistral-large", "mistral-small", "pixtral"],
        "cohere": ["command-r", "command-r-plus"],
        "together": ["auto"],
        "groq": ["llama-4-scout", "llama-4-maverick", "mixtral-8x7b"],
        "fireworks": ["auto"],
        "perplexity": ["sonar-pro", "sonar-reasoning"],
        "replicate": ["auto"],
        "zai": ["glm-4-plus"],
        "minimax": ["minimax-text-01"],
        "kimi": ["moonshot-v1-8k"],
        "alibaba": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "xiaomi": ["mimo"],
        "custom": ["custom"],
    }
    return MODELS.get(provider, ["auto"])


def get_env_keys() -> list:
    return [
        ("OPENROUTER_API_KEY", "OpenRouter"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("OPENAI_API_KEY", "OpenAI"),
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("GOOGLE_API_KEY", "Google Gemini"),
        ("GEMINI_API_KEY", "Gemini (alt)"),
        ("XAI_API_KEY", "xAI / Grok"),
        ("HF_TOKEN", "Hugging Face"),
        ("MISTRAL_API_KEY", "Mistral"),
        ("COHERE_API_KEY", "Cohere"),
        ("TOGETHER_API_KEY", "Together AI"),
        ("GROQ_API_KEY", "Groq"),
        ("FIREWORKS_API_KEY", "Fireworks"),
        ("PERPLEXITY_API_KEY", "Perplexity"),
        ("REPLICATE_API_TOKEN", "Replicate"),
        ("GLM_API_KEY", "Z.AI / GLM"),
        ("MINIMAX_API_KEY", "MiniMax"),
        ("MINIMAX_CN_API_KEY", "MiniMax CN"),
        ("KIMI_API_KEY", "Kimi / Moonshot"),
        ("DASHSCOPE_API_KEY", "Alibaba DashScope"),
        ("XIAOMI_API_KEY", "Xiaomi MiMo"),
        ("KILOCODE_API_KEY", "Kilo Code"),
        ("OPENCODE_ZEN_API_KEY", "OpenCode Zen"),
        ("OPENCODE_GO_API_KEY", "OpenCode Go"),
        ("VOICE_TOOLS_OPENAI_KEY", "OpenAI TTS/STT"),
        ("ELEVENLABS_API_KEY", "ElevenLabs"),
        ("BWS_ACCESS_TOKEN", "Bitwarden"),
        ("COPILOT_GITHUB_TOKEN", "GitHub Copilot"),
    ]


def get_personalities() -> dict:
    cfg = load_config()
    return cfg.get("agent", {}).get("personalities", {
        "helpful": "You are a helpful, friendly AI assistant.",
        "concise": "You are a concise assistant.",
        "technical": "You are a technical expert.",
        "creative": "You are a creative assistant.",
        "teacher": "You are a patient teacher.",
    })


def get_available_skins() -> list:
    return ["default", "dark", "light", "monokai", "solarized", "dracula", "nord", "github"]


def list_profiles() -> list:
    profiles_dir = HERMES_HOME / "profiles"
    if not profiles_dir.exists():
        return ["default"]
    profiles = ["default"]
    for d in profiles_dir.iterdir():
        if d.is_dir():
            profiles.append(d.name)
    return profiles


def create_profile(name: str) -> str:
    try:
        result = subprocess.run(
            [_hermes_bin(), "profile", "create", name],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip() or f"✅ Профіль '{name}' створено"
    except Exception as e:
        return f"❌ {e}"


def delete_profile(name: str) -> str:
    try:
        result = subprocess.run(
            [_hermes_bin(), "profile", "delete", name],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip() or f"✅ Профіль '{name}' видалено"
    except Exception as e:
        return f"❌ {e}"
