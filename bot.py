"""
GLaDoS — точка входа.

Запуск:  python bot.py

Переменные окружения (рекомендуется):
    GLADOS_TOKEN       — токен бота от @BotFather
    GLADOS_OWNER_ID    — ваш Telegram ID
    GLADOS_PIN         — PIN-код для защиты сессии (пусто = отключён)
"""

import asyncio
import logging
from datetime import date

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import glados
import database as db
from config import (
    BOT_TOKEN, OWNER_ID, SUBSCRIPTION_WARN_DAYS,
    DAILY_CHECK_TIME, BOT_MONITOR_INTERVAL_MIN,
)
from handlers import ALL_ROUTERS, AuthMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("GLaDoS")


# ── Ежедневная проверка подписок ────────────────────────────────────────────
async def check_subscriptions(bot: Bot) -> None:
    due = db.subscriptions_due(SUBSCRIPTION_WARN_DAYS)
    if not due:
        log.info("Подписки: предупреждать не о чём.")
        return

    lines = []
    for s in due:
        try:
            left = (date.fromisoformat(s["end_date"]) - date.today()).days
        except (ValueError, TypeError):
            left = None
        if left is None:
            tail = ""
        elif left < 0:
            tail = f"— истекла {abs(left)} дн. назад"
        elif left == 0:
            tail = "— истекает СЕГОДНЯ"
        else:
            tail = f"— осталось {left} дн."
        lines.append(f"• <b>{s['name']}</b> ({s['service'] or '—'}) до {s['end_date']} {tail}")
        db.mark_notified(s["id"])

    text = glados.warning() + "\n\n" + "\n".join(lines)
    try:
        await bot.send_message(OWNER_ID, text)
        log.info("Предупреждение по %d подпискам отправлено.", len(due))
    except Exception as e:
        log.error("Не удалось отправить предупреждение: %s", e)


# ── Периодический мониторинг ботов ──────────────────────────────────────────
async def monitor_bots(bot: Bot) -> None:
    bots = db.list_bots()
    if not bots:
        return
    down = []
    for b in bots:
        bdata = db.get_bot(b["id"])
        if not bdata or not bdata["token"]:
            continue
        other = Bot(token=bdata["token"])
        try:
            me = await other.get_me()
            db.update_bot_status(b["id"], "online", username=me.username)
        except Exception:
            prev = b["status"]
            db.update_bot_status(b["id"], "error")
            if prev != "error":    # уведомляем только при первом падении
                down.append(b["name"])
        finally:
            await other.session.close()
    if down:
        names = ", ".join(down)
        try:
            await bot.send_message(
                OWNER_ID,
                f"🚨 <b>Мониторинг ботов</b>\n\n"
                f"Перестали отвечать: {names}\n\n"
                "Рекомендую проверить. Хотя, может, им просто надоело.",
            )
        except Exception as e:
            log.error("Не удалось отправить алерт о ботах: %s", e)
    log.info("Мониторинг ботов: %d проверено, %d упали.", len(bots), len(down))


# ── Запуск ──────────────────────────────────────────────────────────────────
async def main() -> None:
    db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    auth = AuthMiddleware()
    dp.message.outer_middleware(auth)
    dp.callback_query.outer_middleware(auth)

    for r in ALL_ROUTERS:
        dp.include_router(r)

    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить GLaDoS"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="cancel", description="Отменить текущий ввод"),
    ])

    scheduler = AsyncIOScheduler()

    # Проверка подписок — ежедневно
    hh, mm = (int(x) for x in DAILY_CHECK_TIME.split(":"))
    scheduler.add_job(check_subscriptions, "cron", hour=hh, minute=mm, args=[bot])
    log.info("Проверка подписок: ежедневно в %s.", DAILY_CHECK_TIME)

    # Мониторинг ботов — каждые N минут
    if BOT_MONITOR_INTERVAL_MIN > 0:
        scheduler.add_job(monitor_bots, "interval",
                          minutes=BOT_MONITOR_INTERVAL_MIN, args=[bot])
        log.info("Мониторинг ботов: каждые %d мин.", BOT_MONITOR_INTERVAL_MIN)

    scheduler.start()
    log.info("GLaDoS онлайн. Владелец: %s", OWNER_ID)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("GLaDoS отключается. Тесты приостановлены.")
