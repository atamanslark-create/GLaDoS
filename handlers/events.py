"""
GLaDoS — История событий.
Лента алертов, команд и изменений статуса.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db

log = logging.getLogger("GLaDoS.events")
router = Router()

EVENT_ICONS = {
    "command": "⚙️",
    "alert": "🚨",
    "status_change": "🔄",
    "error": "❌",
    "report": "📊",
}

SEVERITY_ICONS = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
    "success": "✅",
    "failed": "❌",
}

def _build_events_text(event_type: str = None, limit: int = 20) -> str:
    try:
        logs = db.get_audit_logs(event_type=event_type, limit=limit)
    except:
        logs = []

    if not event_type:
        title = "📋 *История событий*"
    else:
        icon = EVENT_ICONS.get(event_type, "📌")
        title = f"{icon} *События: {event_type}*"

    if not logs:
        return f"{title}\n\nСобытий не найдено."

    lines = [title, ""]
    for log_entry in logs:
        event_icon = EVENT_ICONS.get(log_entry["event_type"], "📌")
        status_icon = SEVERITY_ICONS.get(log_entry["status"], "⚪")
        
        bot_name = log_entry.get("bot_name") or f"Bot#{log_entry.get('bot_id', '?')}"
        action = log_entry.get("action", "")
        timestamp = log_entry.get("timestamp", "")[:16]

        lines.append(f"{event_icon} {status_icon} `{timestamp}`")
        lines.append(f"  *{bot_name}*: {action}")
        lines.append("")

    return "\n".join(lines)

def _build_events_keyboard(current_filter: str = None) -> object:
    kb = InlineKeyboardBuilder()
    filters = [
        ("⚙️ Команды", "command"),
        ("🚨 Алерты", "alert"),
        ("🔄 Статусы", "status_change"),
        ("📋 Все", None),
    ]
    for label, f in filters:
        if f == current_filter:
            label = f"• {label} •"
        kb.button(text=label, callback_data=f"events:filter:{f or 'all'}")

    kb.button(text="← Меню", callback_data="menu:main")
    kb.adjust(2, 2, 1)
    return kb.as_markup()

@router.callback_query(F.data == "events:show")
async def show_events(call: CallbackQuery):
    text = _build_events_text()
    await call.message.edit_text(
        text,
        reply_markup=_build_events_keyboard(),
        parse_mode="Markdown"
    )
    await call.answer()

@router.callback_query(F.data.startswith("events:filter:"))
async def filter_events(call: CallbackQuery):
    filter_val = call.data.split(":", 2)[2]
    event_type = None if filter_val == "all" else filter_val
    text = _build_events_text(event_type=event_type)
    try:
        await call.message.edit_text(
            text,
            reply_markup=_build_events_keyboard(current_filter=event_type),
            parse_mode="Markdown"
        )
    except:
        pass
    await call.answer()