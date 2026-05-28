#!/usr/bin/env bash
# GLaDoS — автоустановщик (Linux / macOS)
# Запуск: bash install.sh

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}$*${NC}"; }

echo ""
echo -e "${BOLD}  ██████╗ ██╗      █████╗ ██████╗  ██████╗ ███████╗${NC}"
echo -e "${BOLD}  ██╔════╝ ██║     ██╔══██╗██╔══██╗██╔═══██╗██╔════╝${NC}"
echo -e "${BOLD}  ██║  ███╗██║     ███████║██║  ██║██║   ██║███████╗${NC}"
echo -e "${BOLD}  ██║   ██║██║     ██╔══██║██║  ██║██║   ██║╚════██║${NC}"
echo -e "${BOLD}  ╚██████╔╝███████╗██║  ██║██████╔╝╚██████╔╝███████║${NC}"
echo -e "${BOLD}   ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚══════╝${NC}"
echo ""
echo -e "${BOLD}  Автоустановщик v2.0  (Linux / macOS)${NC}"
echo "  ════════════════════════════════════════════════════"
echo ""

# ── 1. Проверка Python ────────────────────────────────────────────────────────
section "[1/6] Проверка Python"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null || echo False)
        if [ "$VER" = "True" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Требуется Python 3.10+. Установите его и повторите."
fi
info "Используется: $PYTHON ($($PYTHON --version))"

# ── 2. Создание виртуального окружения ───────────────────────────────────────
section "[2/6] Виртуальное окружение"
VENV_DIR="$(pwd)/venv"
if [ ! -d "$VENV_DIR" ]; then
    info "Создание venv в $VENV_DIR ..."
    $PYTHON -m venv "$VENV_DIR"
else
    info "venv уже существует: $VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
info "venv активирован"

# ── 3. Установка / обновление зависимостей ───────────────────────────────────
section "[3/6] Установка зависимостей"

info "Обновление pip..."
pip install --quiet --upgrade pip
info "pip обновлён"

echo ""
info "Установка пакетов из requirements.txt:"
echo ""

# Устанавливаем с прогрессом (--progress-bar on по умолчанию)
pip install --upgrade -r requirements.txt

echo ""
info "Все зависимости установлены и актуальны"

# ── 4. Настройка .env ────────────────────────────────────────────────────────
section "[4/6] Конфигурация"
if [ ! -f ".env" ]; then
    cp .env.example .env

    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  Настройка токена и владельца                        │"
    echo "  │  (Enter чтобы пропустить и заполнить вручную)        │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo ""

    read -r -p "  Токен бота (@BotFather): " TOKEN
    read -r -p "  Ваш Telegram ID (@userinfobot): " OWNER

    if [ -n "$TOKEN" ] && [ -n "$OWNER" ]; then
        sed -i "s|^GLADOS_TOKEN=.*|GLADOS_TOKEN=${TOKEN}|" .env
        sed -i "s|^GLADOS_OWNER_ID=.*|GLADOS_OWNER_ID=${OWNER}|" .env
        info ".env сохранён"
    else
        warn "Пустые значения — .env не заполнен. Отредактируйте вручную: nano .env"
    fi
else
    info ".env уже существует, пропускаем"
fi

# ── 5. Создание директорий ────────────────────────────────────────────────────
section "[5/6] Директории"
mkdir -p data/files
info "data/ и data/files/ готовы"

# ── 6. Скрипты запуска + systemd ─────────────────────────────────────────────
section "[6/6] Скрипты запуска"

INSTALL_DIR="$(pwd)"

# start.sh
cat > start.sh <<'STARTSCRIPT'
#!/usr/bin/env bash
# GLaDoS — быстрый запуск
cd "$(dirname "$0")"
source venv/bin/activate
echo "  Запуск GLaDoS... (Ctrl+C для остановки)"
python bot.py
STARTSCRIPT
chmod +x start.sh
info "start.sh создан"

# update.sh
cat > update.sh <<'UPDATESCRIPT'
#!/usr/bin/env bash
# GLaDoS — обновление зависимостей
set -euo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
echo "Обновление зависимостей GLaDoS..."
pip install --quiet --upgrade pip
pip install --upgrade -r requirements.txt
echo "[OK] Все зависимости обновлены"
UPDATESCRIPT
chmod +x update.sh
info "update.sh создан"

# Systemd (опционально, только на Linux с root)
CURRENT_USER="$(whoami)"
if command -v systemctl &>/dev/null; then
    if [ "$CURRENT_USER" != "root" ]; then
        warn "Для systemd-сервиса нужен root (sudo bash install.sh)"
    else
        read -r -p "  Установить как systemd-сервис? [y/N]: " INSTALL_SERVICE
        if [[ "${INSTALL_SERVICE:-}" =~ ^[Yy]$ ]]; then
            SERVICE_USER="${SUDO_USER:-$CURRENT_USER}"
            SERVICE_FILE="/etc/systemd/system/glados.service"
            cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=GLaDoS Telegram Bot
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/bot.py
Restart=always
RestartSec=5
EnvironmentFile=${INSTALL_DIR}/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
            systemctl daemon-reload
            systemctl enable glados
            info "Сервис установлен: glados.service"
            info "Управление: systemctl start|stop|status glados"
            info "Логи:       journalctl -u glados -f"
        fi
    fi
fi

# ── Итог ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅ Установка завершена!${NC}"
echo -e "${GREEN}${BOLD}  ════════════════════════════════════════════════════${NC}"
echo ""
echo "  Запуск бота:"
echo "    ./start.sh             — запустить"
echo "    ./update.sh            — обновить зависимости"
echo ""
if command -v systemctl &>/dev/null && systemctl is-enabled glados &>/dev/null 2>&1; then
    echo "  Или через systemd:"
    echo "    systemctl start glados"
    echo "    journalctl -u glados -f"
    echo ""
fi
