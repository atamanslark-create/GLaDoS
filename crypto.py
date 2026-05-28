"""
GLaDoS — шифрование чувствительных данных.

Пароли, токены чужих ботов и приватные заметки хранятся в базе
в зашифрованном виде (Fernet / AES-128 в режиме CBC + HMAC).

Ключ генерируется автоматически при первом запуске и лежит в
data/secret.key. ЕСЛИ ВЫ ПОТЕРЯЕТЕ ЭТОТ ФАЙЛ — расшифровать
данные будет невозможно. Храните его так же бережно, как я храню
обиды.
"""

import os
from cryptography.fernet import Fernet, InvalidToken

from config import KEY_PATH


def _load_or_create_key() -> bytes:
    # Ключ можно задать и через переменную окружения (приоритетнее файла)
    env_key = os.getenv("GLADOS_FERNET_KEY")
    if env_key:
        return env_key.encode()

    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()

    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    try:
        os.chmod(KEY_PATH, 0o600)  # доступ только владельцу
    except OSError:
        pass
    return key


_fernet = Fernet(_load_or_create_key())


def encrypt(text: str | None) -> str | None:
    if text is None or text == "":
        return text
    return _fernet.encrypt(text.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if token is None or token == "":
        return token
    try:
        return _fernet.decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return "‹не удалось расшифровать›"
