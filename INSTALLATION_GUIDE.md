# Полное расширение GLaDoS + mini-bot

## 📦 Что добавляется:

### 1. ⚙️ **Командная система**
- Отправка команд из GLaDoS на mini-bot
- История выполнения команд
- Двойное подтверждение для опасных команд
- Аудит всех действий

### 2. 📊 **Веб-панель**
- Порт: 7777
- Логин: slark / пароль: 8l99ujqF
- Графики CPU/RAM/Диск за 7 дней
- Таблица всех ботов
- Real-time обновление

### 3. 🔔 **Умные алерты**
- CPU: ⚠️ 80% / 🔴 90%
- RAM: ⚠️ 80% / 🔴 85%
- Диск: ⚠️ 85% / 🔴 90%
- Отслеживание перезагрузок сервисов
- Интеллектуальные уведомления (не каждый раз)

### 4. 📝 **История и аудит**
- 90 дней хранения
- Фильтрация по дате, боту, типу события
- Экспорт в CSV
- Полный лог всех действий

---

## 🔧 Установка

### STEP 1: Обновить database.py

Добавьте эти таблицы в функцию `init_db()`:

```sql
CREATE TABLE IF NOT EXISTS bot_commands (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id      INTEGER NOT NULL,
    command     TEXT NOT NULL,
    args        TEXT,
    user_id     INTEGER,
    status      TEXT DEFAULT 'pending',
    result      TEXT,
    created_at  TEXT NOT NULL,
    executed_at TEXT,
    FOREIGN KEY(bot_id) REFERENCES managed_bots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    bot_id      INTEGER,
    user_id     INTEGER,
    action      TEXT,
    details     TEXT,
    status      TEXT DEFAULT 'success',
    timestamp   TEXT NOT NULL,
    FOREIGN KEY(bot_id) REFERENCES managed_bots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bot_commands_bot_id ON bot_commands(bot_id);
CREATE INDEX IF NOT EXISTS idx_bot_commands_status ON bot_commands(status);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_bot_id ON audit_log(bot_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
```

+ Добавьте функции из `database_commands.py`

---

### STEP 2: Добавить обработчик команд в GLaDoS

1. Скопируй `handlers_commands.py` в `D:\GLaDoS\handlers\`
2. Обнови `handlers/__init__.py`:

```python
from . import commands
# В ALL_ROUTERS:
commands.router,
```

3. Обнови `keyboards.py` - добавь в main_menu():

```python
kb.button(text="⚙️ Команды", callback_data="commands:list")
```

---

### STEP 3: Установить Flask для веб-панели

```bash
pip install flask flask-basicauth matplotlib
```

---

### STEP 4: Запустить веб-панель

Создай `web_dashboard.py` на VPS или Windows

---

## 🚀 Запуск

```bash
# GLaDoS
python bot.py

# Веб-панель (в отдельном окне)
python web_dashboard.py
```

Панель: `http://localhost:7777`

---

## ✅ Проверка

1. GLaDoS онлайн → раздел "⚙️ Команды"
2. Выбери бота → выбери команду → подтверди
3. Проверь историю в "📋 История"
4. Открой http://localhost:7777 (слумай/пароль)

---

Готовы?
