"""
GLaDoS — Карта серверов.
Показывает статус всех VPS одним экраном.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db

log = logging.getLogger("GLaDoS.server_map")
router = Router()

def _bar(percent: float, width: int = 10) -> str:
    filled = int((percent / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    if percent >= 90:
        return f"🔴 {bar} {percent:.0f}%"
    elif percent >= 80:
        return f"🟡 {bar} {percent:.0f}%"
    else:
        return f"🟢 {bar} {percent:.0f}%"

def _status_icon(status: str) -> str:
    return {"online": "🟢", "offline": "🔴", "error": "⚠️"}.get(status, "⚪")

def _build_server_map_text() -> str:
    bots = db.list_bots()
    if not bots:
        return "🗺️ *Карта серверов*\n\nНет зарегистрированных серверов."

    lines = ["🗺️ *Карта серверов*\n"]
    for bot in bots:
        # Конвертируем Row в dict
        bot_dict = dict(bot) if hasattr(bot, 'keys') else bot
        
        icon = _status_icon(bot_dict.get("status", "unknown"))
        tag = f" `[{bot_dict.get('tag', '')}]`" if bot_dict.get("tag") else ""
        lines.append(f"{icon} *{bot_dict['name']}*{tag}")

        latest = db.get_latest_report(bot_dict["id"])
        if latest and bot_dict.get("status") == "online":
            try:
                import json
                details = json.loads(latest["details"]) if isinstance(latest.get("details"), str) else {}
                cpu = details.get("cpu_percent")
                ram = details.get("memory_percent")
                disk = details.get("disk_percent")
                
                if cpu is not None:
                    lines.append(f"  CPU  {_bar(float(cpu))}")
                if ram is not None:
                    lines.append(f"  RAM  {_bar(float(ram))}")
                if disk is not None:
                    lines.append(f"  Disk {_bar(float(disk))}")
            except:
                pass
        elif bot_dict.get("status") == "offline":
            lines.append("  📴 Офлайн")
        lines.append("")

    online = sum(1 for b in bots if dict(b).get("status") == "online")
    lines.append(f"━━━━━━━━━━━━━━━━━━")
    lines.append(f"Итого: *{online}/{len(bots)}* онлайн")
    return "\n".join(lines)

def _build_map_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="server_map:refresh")
    kb.button(text="← Меню", callback_data="menu:main")
    kb.adjust(2)
    return kb.as_markup()

@router.callback_query(F.data == "server_map:show")
async def show_server_map(call: CallbackQuery):
    text = _build_server_map_text()
    await call.message.edit_text(
        text,
        reply_markup=_build_map_keyboard(),
        parse_mode="Markdown"
    )
    await call.answer()

@router.callback_query(F.data == "server_map:refresh")
async def refresh_server_map(call: CallbackQuery):
    text = _build_server_map_text()
    try:
        await call.message.edit_text(
            text,
            reply_markup=_build_map_keyboard(),
            parse_mode="Markdown"
        )
    except:
        pass
    await call.answer("✅ Обновлено")