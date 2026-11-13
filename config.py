import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "0") or 0)

DASHBOARD_KEY = os.getenv("DASHBOARD_KEY", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")

HORARIOS = {
    "manha": os.getenv("HORARIO_MANHA", "08:00"),
    "tarde": os.getenv("HORARIO_TARDE", "14:30"),
    "noite": os.getenv("HORARIO_NOITE", "21:30"),
}
RESUMO_SEMANAL = os.getenv("RESUMO_SEMANAL", "sun 20:00")  # "dia HH:MM"

BOT_MODE = os.getenv("BOT_MODE", "polling").lower()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

_db = Path(os.getenv("DB_PATH", "data/tracking.db"))
DB_PATH = _db if _db.is_absolute() else BASE_DIR / _db
