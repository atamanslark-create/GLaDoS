@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================================
::  GLaDoS — автоустановщик (Windows)
::  Запуск: двойной клик или  install.bat  в cmd
:: ============================================================

title GLaDoS Installer
color 0A

echo.
echo  ██████╗ ██╗      █████╗ ██████╗  ██████╗ ███████╗
echo  ██╔════╝ ██║     ██╔══██╗██╔══██╗██╔═══██╗██╔════╝
echo  ██║  ███╗██║     ███████║██║  ██║██║   ██║███████╗
echo  ██║   ██║██║     ██╔══██║██║  ██║██║   ██║╚════██║
echo  ╚██████╔╝███████╗██║  ██║██████╔╝╚██████╔╝███████║
echo   ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚══════╝
echo.
echo  Автоустановщик v2.0  (Windows)
echo  ════════════════════════════════════════════════════
echo.

:: ── 1. Проверка Python ──────────────────────────────────────────────────────
echo [1/6] Проверка Python...

set PYTHON=

:: Пробуем py launcher (рекомендуется для Windows)
py -3 --version >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=2" %%v in ('py -3 --version 2^>^&1') do set PYVER=%%v
    set PYTHON=py -3
    goto :python_found
)

:: Пробуем python
python --version >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    set PYTHON=python
    goto :python_found
)

:: Пробуем python3
python3 --version >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=2" %%v in ('python3 --version 2^>^&1') do set PYVER=%%v
    set PYTHON=python3
    goto :python_found
)

echo.
echo  [ОШИБКА] Python не найден!
echo.
echo  Скачайте Python 3.10+ с https://www.python.org/downloads/
echo  При установке отметьте "Add Python to PATH"
echo.
pause
exit /b 1

:python_found
:: Проверяем версию >= 3.10
%PYTHON% -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ОШИБКА] Требуется Python 3.10+, найден %PYVER%
    echo  Скачайте новую версию: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo  [OK] Python %PYVER%

:: ── 2. Виртуальное окружение ─────────────────────────────────────────────────
echo.
echo [2/6] Виртуальное окружение...

if exist "venv\Scripts\activate.bat" (
    echo  [OK] venv уже существует
) else (
    echo  Создание venv...
    %PYTHON% -m venv venv
    if %errorlevel% neq 0 (
        echo  [ОШИБКА] Не удалось создать venv
        pause
        exit /b 1
    )
    echo  [OK] venv создан
)

call venv\Scripts\activate.bat
echo  [OK] venv активирован

:: ── 3. Установка / обновление зависимостей ───────────────────────────────────
echo.
echo [3/6] Установка зависимостей...
echo.

echo  Обновление pip...
python -m pip install --quiet --upgrade pip
if %errorlevel% neq 0 (
    echo  [ПРЕДУПРЕЖДЕНИЕ] Не удалось обновить pip, продолжаем...
)
echo  [OK] pip обновлён

echo.
echo  Установка пакетов из requirements.txt:
echo  (это может занять несколько минут)
echo.
python -m pip install --upgrade -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  [ОШИБКА] Не удалось установить зависимости
    echo  Проверьте подключение к интернету и повторите
    pause
    exit /b 1
)
echo.
echo  [OK] Все зависимости установлены

:: ── 4. Создание директорий ────────────────────────────────────────────────────
echo.
echo [4/6] Создание директорий...

if not exist "data" mkdir data
if not exist "data\files" mkdir data\files
echo  [OK] data\ и data\files\ готовы

:: ── 5. Настройка .env ────────────────────────────────────────────────────────
echo.
echo [5/6] Конфигурация...

if exist ".env" (
    echo  [OK] .env уже существует, пропускаем
    goto :env_done
)

copy .env.example .env >nul
echo  [OK] .env создан из шаблона

echo.
echo  ┌─────────────────────────────────────────────────────┐
echo  │  Настройка токена и владельца                        │
echo  │  (нажмите Enter чтобы пропустить и заполнить вручную)│
echo  └─────────────────────────────────────────────────────┘
echo.

set /p BOT_TOKEN="  Токен бота (@BotFather): "
set /p OWNER_ID="  Ваш Telegram ID (@userinfobot): "

if "!BOT_TOKEN!"=="" goto :env_manual
if "!OWNER_ID!"=="" goto :env_manual

:: Записываем в .env через Python (надёжнее чем powershell для кодировок)
python -c "
import re, sys
token = sys.argv[1]
owner = sys.argv[2]
with open('.env', 'r', encoding='utf-8') as f:
    content = f.read()
content = re.sub(r'^GLADOS_TOKEN=.*', 'GLADOS_TOKEN=' + token, content, flags=re.M)
content = re.sub(r'^GLADOS_OWNER_ID=.*', 'GLADOS_OWNER_ID=' + owner, content, flags=re.M)
with open('.env', 'w', encoding='utf-8') as f:
    f.write(content)
" "!BOT_TOKEN!" "!OWNER_ID!"

echo  [OK] .env сохранён
goto :env_done

:env_manual
echo  [!] Заполните .env вручную перед запуском бота
echo      Откройте файл .env в блокноте и укажите GLADOS_TOKEN и GLADOS_OWNER_ID

:env_done

:: ── 6. Ярлыки запуска ────────────────────────────────────────────────────────
echo.
echo [6/6] Создание скриптов запуска...

:: Создаём start.bat
(
    echo @echo off
    echo chcp 65001 ^>nul 2^>^&1
    echo title GLaDoS Bot
    echo cd /d "%%~dp0"
    echo call venv\Scripts\activate.bat
    echo echo.
    echo echo  Запуск GLaDoS...
    echo echo  Для остановки нажмите Ctrl+C
    echo echo.
    echo python bot.py
    echo pause
) > start.bat
echo  [OK] start.bat создан

:: Создаём update.bat (обновление зависимостей)
(
    echo @echo off
    echo chcp 65001 ^>nul 2^>^&1
    echo title GLaDoS Updater
    echo cd /d "%%~dp0"
    echo call venv\Scripts\activate.bat
    echo echo Обновление зависимостей GLaDoS...
    echo python -m pip install --quiet --upgrade pip
    echo python -m pip install --upgrade -r requirements.txt
    echo echo.
    echo echo [OK] Обновление завершено
    echo pause
) > update.bat
echo  [OK] update.bat создан

:: ── Предложение добавить в автозапуск Windows ─────────────────────────────────
echo.
set /p ADD_TASK="  Добавить GLaDoS в автозапуск Windows? [y/N]: "
if /i "!ADD_TASK!"=="y" (
    set TASK_CMD="%CD%\venv\Scripts\python.exe" "%CD%\bot.py"
    schtasks /create /tn "GLaDoS Bot" /tr "!TASK_CMD!" /sc ONLOGON /rl HIGHEST /f >nul 2>&1
    if %errorlevel%==0 (
        echo  [OK] Задача автозапуска создана (Планировщик заданий)
        echo       Управление: Планировщик заданий -> GLaDoS Bot
    ) else (
        echo  [!] Не удалось создать задачу. Попробуйте запустить от администратора.
    )
)

:: ── Итог ─────────────────────────────────────────────────────────────────────
echo.
echo  ════════════════════════════════════════════════════
echo  [OK] Установка завершена!
echo  ════════════════════════════════════════════════════
echo.
echo  Запуск бота:
echo    start.bat           — запустить бота
echo    update.bat          — обновить зависимости
echo.
if not exist ".env" goto :no_env_warn
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
t = os.getenv('GLADOS_TOKEN','')
o = os.getenv('GLADOS_OWNER_ID','')
if not t or not o:
    print('  [!] .env не заполнен — отредактируйте его перед запуском')
else:
    print('  [OK] .env настроен')
" 2>nul
goto :final_pause

:no_env_warn
echo  [!] Заполните .env перед запуском!
echo      Укажите GLADOS_TOKEN и GLADOS_OWNER_ID

:final_pause
echo.
pause
endlocal
