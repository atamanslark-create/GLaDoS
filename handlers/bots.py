"""
GLaDoS — раздел «Боты».
Управление другими ботами по их токену: проверка статуса (getMe),
отправка сообщения владельцу через выбранного бота.
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
SECTION = "bot"


class AddBot(StatesGroup):
    name = State()
    token = State()
    note = State()


class SendMsg(StatesGroup):
    text = State()


def _label(r) -> str:
    icon = {"online": "🟢", "offline": "🔴", "error": "⚠️"}.get(r["status"], "⚪")
    return f"{icon} {r['name']}"


async def _show_list(target: CallbackQuery):
    rows = db.list_bots()
    if not rows:
        await target.message.edit_text(
            "🤖 <b>Управляемые боты</b>\n\n" + glados.empty(),
            reply_markup=kb.section_menu(SECTION, "➕ Добавить бота"),
        )
    else:
        await target.message.edit_text(
            "🤖 <b>Управляемые боты</b>\n\n"
            "🟢 проверен · 🔴 ошибка токена · ⚪ не проверялся\n\nВыберите бота:",
            reply_markup=kb.list_keyboard(SECTION, rows, _label, "➕ Добавить бота"),
        )
    await target.answer()


@router.callback_query(F.data == "bot:list")
async def bot_list(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_list(call)


async def _show_bot(message, bid: int):
    """Отображает карточку бота (используется из нескольких мест)."""
    b = db.get_bot(bid)
    if not b:
        return
    text = (
        f"🤖 <b>{b['name']}</b>\n\n"
        f"Username: {('@' + b['username']) if b['username'] else '—'}\n"
        f"Статус: {b['status']}\n"
        f"Токен: <code>{_mask(b['token'])}</code>\n"
        f"Заметка: {b['note'] or '—'}\n"
        f"Добавлен: {b['created_at']}"
    )
    extra = [
        ("🔍 Проверить (getMe)", f"bot:check:{bid}"),
        ("✉️ Отправить мне сообщение", f"bot:msg:{bid}"),
    ]
    try:
        await message.edit_text(text, reply_markup=kb.item_actions(SECTION, bid, extra))
    except Exception:
        await message.answer(text, reply_markup=kb.item_actions(SECTION, bid, extra))


@router.callback_query(F.data.startswith("bot:view:"))
async def bot_view(call: CallbackQuery):
    bid = int(call.data.split(":")[2])
    b = db.get_bot(bid)
    if not b:
        await call.answer("Бот исчез.", show_alert=True)
        return await _show_list(call)
    await _show_bot(call.message, bid)
    await call.answer()


def _mask(token: str | None) -> str:
    if not token:
        return "—"
    if len(token) <= 12:
        return "••••"
    return token[:6] + "…" + token[-4:]


@router.callback_query(F.data.startswith("bot:check:"))
async def bot_check(call: CallbackQuery):
    bid = int(call.data.split(":")[2])
    b = db.get_bot(bid)
    if not b or not b["token"]:
        return await call.answer("Нет токена для проверки.", show_alert=True)
    await call.answer("Проверяю...")
    other = Bot(token=b["token"])
    try:
        me = await other.get_me()
        db.update_bot_status(bid, "online", username=me.username)
        await call.message.answer(
            glados.ok(f"Бот жив: @{me.username} (id {me.id}). Какое облегчение.")
        )
    except Exception as e:
        db.update_bot_status(bid, "error")
        await call.message.answer(glados.err(f"Бот не отвечает. Токен мёртв?\n<code>{e}</code>"))
    finally:
        await other.session.close()
    await _show_bot(call.message, bid)


@router.callback_query(F.data.startswith("bot:msg:"))
async def bot_msg_start(call: CallbackQuery, state: FSMContext):
    bid = int(call.data.split(":")[2])
    await state.set_state(SendMsg.text)
    await state.update_data(bid=bid)
    await call.message.edit_text(
        "✉️ Введите текст. Я отправлю его вам <b>от имени этого бота</b>.\n"
        "(Сработает, только если вы хоть раз запускали того бота командой /start.)",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(SendMsg.text)
async def bot_msg_send(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    b = db.get_bot(data["bid"])
    if not b or not b["token"]:
        return await message.answer(glados.err("Токен пропал."))
    other = Bot(token=b["token"])
    try:
        await other.send_message(OWNER_ID, message.text)
        await message.answer(glados.ok("Сообщение доставлено через подчинённого бота."),
                             reply_markup=kb.back_to_menu())
    except Exception as e:
        await message.answer(
            glados.err(f"Не вышло. Скорее всего, вы не запускали того бота.\n<code>{e}</code>"),
            reply_markup=kb.back_to_menu(),
        )
    finally:
        await other.session.close()


@router.callback_query(F.data.startswith("bot:del:"))
async def bot_del(call: CallbackQuery):
    bid = int(call.data.split(":")[2])
    await call.message.edit_text(
        "Убрать этого бота из-под надзора?",
        reply_markup=kb.confirm_delete(SECTION, bid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("bot:delyes:"))
async def bot_delyes(call: CallbackQuery):
    bid = int(call.data.split(":")[2])
    db.delete_bot(bid)
    await call.answer("Освобождён. Или удалён. Зависит от точки зрения.")
    await _show_list(call)


# --- Мастер добавления ------------------------------------------------------
@router.callback_query(F.data == "bot:add")
async def bot_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddBot.name)
    await call.message.edit_text(
        "🤖 <b>Новый подчинённый бот</b>\n\nШаг 1/3. <b>Название</b> бота:",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(AddBot.name)
async def bot_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddBot.token)
    await message.answer(
        "Шаг 2/3. <b>Токен</b> бота (от @BotFather). Он будет зашифрован:",
        reply_markup=kb.cancel_only(),
    )


@router.message(AddBot.token)
async def bot_token(message: Message, state: FSMContext):
    await state.update_data(token=message.text.strip())
    await state.set_state(AddBot.note)
    await message.answer("Шаг 3/3. <b>Заметка</b> (или «-»):", reply_markup=kb.cancel_only())


@router.message(AddBot.note)
async def bot_note(message: Message, state: FSMContext):
    val = message.text.strip()
    data = await state.get_data()
    db.add_bot(name=data["name"], token=data["token"], note="" if val == "-" else val)
    await state.clear()
    await message.answer(
        glados.ok("Бот добавлен. Откройте его карточку и нажмите «Проверить»."),
        reply_markup=kb.back_to_menu(),
    )
