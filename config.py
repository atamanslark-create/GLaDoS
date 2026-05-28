"""
GLaDoS — конфигурация.

Все значения задаются через переменные окружения или файл .env
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Каталоги ---------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("GLADOS_DATA_DIR", str(BASE_DIR / "data")))
FILES_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "glados.db"
KEY_PATH = DATA_DIR / "secret.key"

DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)

# --- Telegram ---------------------------------------------------------------
BOT_TOKEN = os.getenv("GLADOS_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError(
        "GLADOS_TOKEN не задан. Укажите токен в .env или переменной окружения."
    )

OWNER_ID_RAW = os.getenv("GLADOS_OWNER_ID", "")
if not OWNER_ID_RAW:
    raise RuntimeError(
        "GLADOS_OWNER_ID не задан. Укажите ваш Telegram user ID в .env."
    )
OWNER_ID = int(OWNER_ID_RAW)

# --- PIN-авторизация --------------------------------------------------------
# Пустая строка = PIN отключён.
PIN_CODE = os.getenv("GLADOS_PIN", "")
PIN_TIMEOUT_MIN = int(os.getenv("GLADOS_PIN_TIMEOUT", "30"))  # минут

# --- Подписки ---------------------------------------------------------------
SUBSCRIPTION_WARN_DAYS = int(os.getenv("GLADOS_WARN_DAYS", "5"))
DAILY_CHECK_TIME = os.getenv("GLADOS_CHECK_TIME", "10:00")

# --- Мониторинг ботов -------------------------------------------------------
BOT_MONITOR_INTERVAL_MIN = int(os.getenv("GLADOS_BOT_MONITOR_MIN", "60"))

# --- Файлы ------------------------------------------------------------------
MAX_FILE_MB = int(os.getenv("GLADOS_MAX_FILE_MB", "20"))
