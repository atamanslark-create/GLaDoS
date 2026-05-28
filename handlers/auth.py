"""
GLaDoS — PIN авторизация.
Запрашивает PIN при каждом /start, очищает историю чата.
"""

import time
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import CommandStart

from config import PIN_CODE, OWNER_ID

log = logging.getLogger("GLaDoS.auth")
router = Router()

_sessions: dict = {}


def is_authorized(user_id: int) -> bool:
    return user_id in _sessions

def authorize(user_id: int):
    _sessions[user_id] = time.time()

def deauthorize(user_id: int):
    _sessions.pop(user_id, None)


class PinState(StatesGroup):
    waiting = State()


async def _clear_chat(message: Message):
    chat_id = message.chat.id
    msg_id = message.message_id
    deleted = 0
    for i in range(1, 51):
        try:
            await message.bot.delete_message(chat_id, msg_id - i)
            deleted += 1
        except Exception:
            pass
    log.info(f"Cleared {deleted} messages for {message.from_user.id}")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start — деавторизация + запрос PIN."""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Доступ запрещён.")
        return

    deauthorize(message.from_user.id)
    await state.clear()

    await _clear_chat(message)

    try:
        await message.delete()
    except Exception:
        pass

    if not PIN_CODE:
        from handlers.common import show_main_menu
        await show_main_menu(message)
        return

    await state.set_state(PinState.waiting)
    sent = await message.answer(
        "🔐 <b>GLaDoS CORE</b>\n\nВведите PIN-код:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.update_data(pin_msg_id=sent.message_id)


@router.message(PinState.waiting)
async def check_pin(message: Message, state: FSMContext):
    """Проверка PIN-кода."""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Доступ запрещён.")
        await state.clear()
        return

    entered = message.text.strip() if message.text else ""

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    pin_msg_id = data.get("pin_msg_id")

    if entered == PIN_CODE:
        authorize(message.from_user.id)
        await state.clear()

        try:
            await message.bot.delete_message(message.chat.id, pin_msg_id)
        except Exception:
            pass

        log.info(f"User {message.from_user.id} authorized successfully")

        from handlers.common import show_main_menu
        await show_main_menu(message)

    else:
        log.warning(f"Wrong PIN from user {message.from_user.id}: '{entered}'")
        await message.answer(
            "❌ Неверный PIN.\n\nПопробуйте ещё раз:",
            parse_mode="HTML"
        )
