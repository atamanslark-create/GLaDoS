"""
GLaDoS — раздел «Отчёты ботов».
Приём, хранение и отображение отчётов от подключённых ботов (mini-bot и др.)
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import glados
import keyboards as kb
import database as db
from config import OWNER_ID

router = Router()
SECTION = "reports"


def _bot_status_icon(status: str) -> str:
    """Get status icon for a bot."""
    return {"online": "🟢", "offline": "🔴", "error": "⚠️"}.get(status, "⚪")


def _severity_icon(severity: str) -> str:
    """Get icon for report severity."""
    return {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🔵",
    }.get(severity, "⚪")


async def _show_reports_menu(target: CallbackQuery):
    """Показать меню отчётов."""
    bots = db.list_bots()

    if not bots:
        await target.message.edit_text(
            "📋 <b>Отчёты ботов</b>\n\n" + glados.empty(),
            reply_markup=kb.back_to_menu(),
        )
        await target.answer()
        return

    # Получить последний отчёт от каждого бота
    text = "📋 <b>Отчёты ботов</b>\n\n"
    text += "Последние отчёты от подключённых ботов:\n\n"

    has_reports = False
    for bot in bots:
        latest = db.get_latest_report(bot["id"])
        status_icon = _bot_status_icon(bot["status"])

        if latest:
            has_reports = True
            severity_icon = _severity_icon(latest["severity"])
            text += f"{status_icon} <b>{bot['name']}</b> {severity_icon}\n"
            text += f"   • {latest['title']}\n"
            text += f"   • {latest['received_at']}\n\n"
        else:
            text += f"{status_icon} <b>{bot['name']}</b>\n"
            text += f"   • Отчётов нет\n\n"

    await target.message.edit_text(
        text.strip(),
        reply_markup=kb.back_to_menu(),
        parse_mode="HTML",
    )
    await target.answer()


async def _show_all_reports(target: CallbackQuery):
    """Показать все отчёты."""
    reports = db.get_all_reports(limit=20)

    if not reports:
        await target.message.edit_text(
            "📊 <b>Все отчёты</b>\n\n" + glados.empty(),
            reply_markup=kb.back_to_menu(),
        )
        await target.answer()
        return

    text = "📊 <b>Все отчёты</b>\n\n"
    for report in reports:
        severity = _severity_icon(report["severity"])
        text += f"{severity} <b>{report['name']}</b>\n"
        text += f"   <i>{report['received_at']}</i>\n"
        text += f"   {report['title']}\n\n"

    await target.message.edit_text(
        text.strip(),
        reply_markup=kb.back_to_menu(),
        parse_mode="HTML",
    )
    await target.answer()


async def _show_critical_reports(target: CallbackQuery):
    """Показать только критические отчёты."""
    reports = db.get_critical_reports(limit=20)

    if not reports:
        await target.message.edit_text(
            "🔴 <b>Критические отчёты</b>\n\n"
            "Критических отчётов не найдено. Всё хорошо.",
            reply_markup=kb.back_to_menu(),
        )
        await target.answer()
        return

    text = "🔴 <b>Критические отчёты</b>\n\n"
    for report in reports:
        text += f"<b>{report['name']}</b>\n"
        text += f"<i>{report['received_at']}</i>\n"
        text += f"⚠️ {report['title']}\n\n"
        if report['content']:
            text += f"<code>{report['content'][:100]}...</code>\n\n"

    await target.message.edit_text(
        text.strip(),
        reply_markup=kb.back_to_menu(),
        parse_mode="HTML",
    )
    await target.answer()


@router.callback_query(F.data == "reports:list")
async def reports_list(call: CallbackQuery):
    """Главное меню отчётов."""
    await _show_reports_menu(call)


@router.callback_query(F.data == "reports:all")
async def reports_all(call: CallbackQuery):
    """Показать все отчёты."""
    await _show_all_reports(call)


@router.callback_query(F.data == "reports:critical")
async def reports_critical(call: CallbackQuery):
    """Показать критические отчёты."""
    await _show_critical_reports(call)


@router.callback_query(F.data.startswith("reports:bot:"))
async def reports_by_bot(call: CallbackQuery):
    """Показать отчёты конкретного бота."""
    bot_id = int(call.data.split(":")[2])
    bot = db.get_bot(bot_id)
    reports = db.get_bot_reports(bot_id, limit=10)

    if not bot:
        await call.answer("Бот не найден.", show_alert=True)
        return await _show_reports_menu(call)

    if not reports:
        await call.message.edit_text(
            f"📋 <b>Отчёты от {bot['name']}</b>\n\n"
            "Отчётов не найдено.",
            reply_markup=kb.back_to_menu(),
        )
        await call.answer()
        return

    text = f"📋 <b>Отчёты от {bot['name']}</b>\n\n"
    for report in reports:
        severity = _severity_icon(report["severity"])
        text += f"{severity} {report['received_at']}\n"
        text += f"<b>{report['title']}</b>\n"
        if report['content']:
            text += f"<i>{report['content'][:80]}...</i>\n"
        text += "\n"

    await call.message.edit_text(
        text.strip(),
        reply_markup=kb.back_to_menu(),
        parse_mode="HTML",
    )
    await call.answer()
