#!/usr/bin/env bash
# GLaDoS — автоустановщик (Linux / macOS)
# Запуск: bash install.sh

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
section() { echo -e "\n${BOLD}$*${NC}"; }

# ── 1. Проверка Python ────────────────────────────────────────────────────────
section "1. Проверка Python"
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
section "2. Виртуальное окружение"
VENV_DIR="$(pwd)/venv"
if [ ! -d "$VENV_DIR" ]; then
    info "Создание venv в $VENV_DIR"
    $PYTHON -m venv "$VENV_DIR"
else
    info "venv уже существует: $VENV_DIR"
fi

# Активируем venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
info "venv активирован"

# ── 3. Установка зависимостей ────────────────────────────────────────────────
section "3. Установка зависимостей"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
info "Зависимости установлены"

# ── 4. Настройка .env ────────────────────────────────────────────────────────
section "4. Конфигурация"
if [ ! -f ".env" ]; then
    cp .env.example .env
    warn ".env создан из шаблона. Откройте его и заполните GLADOS_TOKEN и GLADOS_OWNER_ID"
    echo ""
    echo "  nano .env   # или любой другой редактор"
    echo ""

    # Интерактивный ввод
    read -r -p "Введите токен бота (@BotFather): " TOKEN
    read -r -p "Введите ваш Telegram user ID (@userinfobot): " OWNER

    # Записываем в .env
    if [ -n "$TOKEN" ] && [ -n "$OWNER" ]; then
        sed -i "s|^GLADOS_TOKEN=.*|GLADOS_TOKEN=${TOKEN}|" .env
        sed -i "s|^GLADOS_OWNER_ID=.*|GLADOS_OWNER_ID=${OWNER}|" .env
        info ".env сохранён"
    else
        warn "Пустые значения — .env не заполнен. Отредактируйте вручную перед запуском."
    fi
else
    info ".env уже существует, пропускаем"
fi

# ── 5. Создание директорий ────────────────────────────────────────────────────
section "5. Директории"
mkdir -p data/files
info "data/ и data/files/ готовы"

# ── 6. Systemd-сервис (опционально) ──────────────────────────────────────────
section "6. Systemd (опционально)"
SERVICE_FILE="/etc/systemd/system/glados.service"
INSTALL_DIR="$(pwd)"
CURRENT_USER="$(whoami)"

if command -v systemctl &>/dev/null && [ "$CURRENT_USER" != "root" ]; then
    warn "Для установки systemd-сервиса нужны права root. Пропускаем."
    warn "Запустите вручную: sudo bash install.sh --systemd"
elif command -v systemctl &>/dev/null; then
    read -r -p "Установить как systemd-сервис? [y/N]: " INSTALL_SERVICE
    if [[ "$INSTALL_SERVICE" =~ ^[Yy]$ ]]; then
        SERVICE_USER="${SUDO_USER:-$CURRENT_USER}"
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

# ── Готово ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✅ Установка завершена!${NC}"
echo ""
echo "Запуск бота:"
echo "  source venv/bin/activate"
echo "  python bot.py"
echo ""
if command -v systemctl &>/dev/null && systemctl is-enabled glados &>/dev/null 2>&1; then
    echo "Или через systemd:"
    echo "  systemctl start glados"
    echo ""
fi
