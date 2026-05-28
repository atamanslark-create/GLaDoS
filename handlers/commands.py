"""
GLaDoS — раздел «Команды ботам».
Отправка команд, просмотр истории выполнения.
"""

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import glados
import keyboards as kb
import database as db
from config import OWNER_ID

router = Router()
SECTION = "commands"

# Опасные команды требуют двойного подтверждения
DANGEROUS_COMMANDS = {'reboot', 'cleanup logs', 'kill'}


class SendCommand(StatesGroup):
    choose_bot = State()
    choose_command = State()
    enter_args = State()
    confirm = State()


AVAILABLE_COMMANDS = {
    "restart nginx": "Перезагрузить веб-сервер",
    "restart mysql": "Перезагрузить базу данных",
    "restart redis": "Перезагрузить кеш",
    "reboot": "⚠️ ПЕРЕЗАГРУЗИТЬ VPS",
    "cleanup logs": "⚠️ Очистить логи",
    "get top processes": "Топ процессов",
    "get system info": "Информация о системе",
}


async def _show_commands_menu(target: CallbackQuery):
    """Главное меню команд."""
    bots = db.list_bots()

    if not bots:
        await target.message.edit_text(
            "⚙️ <b>Команды ботам</b>\n\n" + glados.empty(),
            reply_markup=kb.back_to_menu(),
        )
        await target.answer()
        return

    text = "⚙️ <b>Команды ботам</b>\n\n"
    text += "Выберите действие:\n\n"

    for bot in bots:
        icon = {"online": "🟢", "offline": "🔴", "error": "⚠️"}.get(bot["status"], "⚪")
        text += f"{icon} {bot['name']}\n"

    buttons = [
        ("📤 Отправить команду", f"{SECTION}:send"),
        ("📋 История команд", f"{SECTION}:history"),
        ("← Назад", "menu:main"),
    ]

    from aiogram.types import InlineKeyboardMarkup
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb_builder = InlineKeyboardBuilder()
    for text_btn, cb in buttons:
        kb_builder.button(text=text_btn, callback_data=cb)
    kb_builder.adjust(1)

    await target.message.edit_text(
        text.strip(),
        reply_markup=kb_builder.as_markup(),
        parse_mode="HTML",
    )
    await target.answer()


async def _show_command_history(target: CallbackQuery):
    """Показать историю команд."""
    logs = db.get_command_history(limit=20)

    if not logs:
        await target.message.edit_text(
            "📋 <b>История команд</b>\n\n"
            "Команд не найдено.",
            reply_markup=kb.back_to_menu(),
        )
        await target.answer()
        return

    text = "📋 <b>История команд</b>\n\n"
    for log in logs:
        status_icon = "✅" if log["status"] == "executed" else "❌" if log["status"] == "failed" else "⏳"
        text += f"{status_icon} <b>{log['name']}</b>\n"
        text += f"   {log['command']}\n"
        text += f"   <i>{log['created_at']}</i>\n\n"

    await target.message.edit_text(
        text.strip(),
        reply_markup=kb.back_to_menu(),
        parse_mode="HTML",
    )
    await target.answer()


@router.callback_query(F.data == "commands:list")
async def commands_list(call: CallbackQuery):
    """Главное меню команд."""
    await _show_commands_menu(call)


@router.callback_query(F.data == "commands:send")
async def commands_send_start(call: CallbackQuery, state: FSMContext):
    """Начать процесс отправки команды."""
    bots = db.list_bots()

    if not bots:
        await call.answer("Нет доступных ботов.", show_alert=True)
        return

    await state.set_state(SendCommand.choose_bot)

    text = "⚙️ <b>Отправить команду</b>\n\n"
    text += "Выберите бот:\n\n"

    from aiogram.types import InlineKeyboardMarkup
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb_builder = InlineKeyboardBuilder()
    for bot in bots:
        icon = {"online": "🟢", "offline": "🔴"}.get(bot["status"], "⚪")
        kb_builder.button(
            text=f"{icon} {bot['name']}",
            callback_data=f"cmd:bot:{bot['id']}"
        )
    kb_builder.button(text="← Отмена", callback_data="menu:cancel")
    kb_builder.adjust(1)

    await call.message.edit_text(text, reply_markup=kb_builder.as_markup(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("cmd:bot:"))
async def commands_choose_bot(call: CallbackQuery, state: FSMContext):
    """Выбрать бота и показать команды."""
    bot_id = int(call.data.split(":")[2])
    bot = db.get_bot(bot_id)

    if not bot:
        await call.answer("Бот не найден.", show_alert=True)
        return

    await state.set_state(SendCommand.choose_command)
    await state.update_data(bot_id=bot_id, bot_name=bot['name'])

    text = f"⚙️ <b>Команды для {bot['name']}</b>\n\n"
    text += "Выберите команду:\n\n"

    from aiogram.types import InlineKeyboardMarkup
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb_builder = InlineKeyboardBuilder()
    for cmd, description in AVAILABLE_COMMANDS.items():
        kb_builder.button(
            text=description,
            callback_data=f"cmd:exec:{cmd}"
        )
    kb_builder.button(text="← Отмена", callback_data="menu:cancel")
    kb_builder.adjust(1)

    await call.message.edit_text(text, reply_markup=kb_builder.as_markup(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("cmd:exec:"))
async def commands_execute(call: CallbackQuery, state: FSMContext):
    """Выполнить команду с подтверждением."""
    command = ":".join(call.data.split(":")[2:])
    data = await state.get_data()

    is_dangerous = any(d in command.lower() for d in DANGEROUS_COMMANDS)

    text = f"⚠️ <b>Подтверждение команды</b>\n\n"
    text += f"<b>Бот:</b> {data['bot_name']}\n"
    text += f"<b>Команда:</b> <code>{command}</code>\n\n"

    if is_dangerous:
        text += "🔴 <b>ОПАСНАЯ КОМАНДА!</b>\n"
        text += "Требуется двойное подтверждение.\n\n"

    from aiogram.types import InlineKeyboardMarkup
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(text="✅ Выполнить", callback_data=f"cmd:confirm:{data['bot_id']}:{command}")
    kb_builder.button(text="❌ Отмена", callback_data="menu:cancel")
    kb_builder.adjust(2)

    await state.update_data(command=command)
    await call.message.edit_text(text, reply_markup=kb_builder.as_markup(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("cmd:confirm:"))
async def commands_confirm(call: CallbackQuery, state: FSMContext):
    """Финальное подтверждение и выполнение команды."""
    parts = call.data.split(":", 3)
    bot_id = int(parts[2])
    command = parts[3]

    data = await state.get_data()

    # Добавить команду в очередь
    cmd_id = db.add_command(
        bot_id=bot_id,
        command=command,
        user_id=call.from_user.id
    )

    # Логировать в аудит
    db.add_audit_log(
        event_type='command',
        bot_id=bot_id,
        user_id=call.from_user.id,
        action=command,
        details=f"Command queued: {command}",
        status='success'
    )

    await state.clear()

    text = f"✅ <b>Команда добавлена в очередь</b>\n\n"
    text += f"ID: <code>{cmd_id}</code>\n"
    text += f"<b>Бот:</b> {data['bot_name']}\n"
    text += f"<b>Команда:</b> <code>{command}</code>\n\n"
    text += "Бот выполнит её при следующей проверке."

    await call.message.edit_text(text, reply_markup=kb.back_to_menu(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "commands:history")
async def commands_history(call: CallbackQuery):
    """История команд."""
    await _show_command_history(call)
