"""
GLaDoS — раздел «Учётные записи».
Логины/пароли (зашифрованы), генератор паролей, автоудаление.
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import glados
import keyboards as kb
import database as db
from utils import generate_password

router = Router()
SECTION = "acc"


class AddAcc(StatesGroup):
    service = State()
    login = State()
    password = State()
    url = State()
    note = State()


def _label(r) -> str:
    return f"🔑 {r['service']} · {r['login'] or '—'}"


async def _show_list(target: CallbackQuery):
    rows = db.list_accounts()
    extra = [("🎲 Генератор паролей", "pwgen:menu")] if True else None
    if not rows:
        await target.message.edit_text(
            "🔐 <b>Учётные записи</b>\n\n" + glados.empty(),
            reply_markup=kb.section_menu(SECTION, "➕ Добавить запись"),
        )
    else:
        await target.message.edit_text(
            "🔐 <b>Учётные записи</b>\n\nПароли скрыты, пока вы их не запросите.\n"
            "Выберите запись:",
            reply_markup=kb.list_keyboard(SECTION, rows, _label,
                                          "➕ Добавить запись", extra),
        )
    await target.answer()


@router.callback_query(F.data == "acc:list")
async def acc_list(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_list(call)


@router.callback_query(F.data.startswith("acc:view:"))
async def acc_view(call: CallbackQuery):
    aid = int(call.data.split(":")[2])
    a = db.get_account(aid)
    if not a:
        await call.answer("Запись исчезла.", show_alert=True)
        return await _show_list(call)
    text = (
        f"🔑 <b>{a['service']}</b>\n\n"
        f"Логин: <code>{a['login'] or '—'}</code>\n"
        f"Пароль: ••••••••\n"
        f"Ссылка: {a['url'] or '—'}\n"
        f"Заметка: {a['note'] or '—'}\n"
        f"Добавлено: {a['created_at']}"
    )
    extra = [("👁 Показать пароль", f"acc:reveal:{aid}")]
    await call.message.edit_text(text, reply_markup=kb.item_actions(SECTION, aid, extra))
    await call.answer()


@router.callback_query(F.data.startswith("acc:reveal:"))
async def acc_reveal(call: CallbackQuery):
    aid = int(call.data.split(":")[2])
    a = db.get_account(aid)
    if not a:
        return await call.answer("Нет такой записи.", show_alert=True)
    await call.answer(f"Логин: {a['login'] or '—'}\nПароль: {a['password'] or '—'}",
                      show_alert=True)


@router.callback_query(F.data.startswith("acc:del:"))
async def acc_del(call: CallbackQuery):
    aid = int(call.data.split(":")[2])
    await call.message.edit_text(
        "Удалить эту учётную запись? Пароль восстановить будет нельзя.",
        reply_markup=kb.confirm_delete(SECTION, aid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("acc:delyes:"))
async def acc_delyes(call: CallbackQuery):
    aid = int(call.data.split(":")[2])
    db.delete_account(aid)
    await call.answer("Удалено без следа.")
    await _show_list(call)


# ── Генератор паролей ───────────────────────────────────────────────────────
@router.callback_query(F.data == "pwgen:menu")
async def pwgen_menu(call: CallbackQuery):
    await call.message.edit_text(
        "🎲 <b>Генератор паролей</b>\n\n"
        "Выберите длину. Пароль появится во всплывающем окне\n"
        "(не сохраняется в истории чата).",
        reply_markup=kb.password_gen_options(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pwgen:"))
async def pwgen_exec(call: CallbackQuery):
    parts = call.data.split(":")
    if len(parts) < 3 or parts[1] == "menu":
        return
    length = int(parts[1])
    use_special = bool(int(parts[2]))
    pwd = generate_password(length, use_special)
    await call.answer(f"🔑 {pwd}", show_alert=True)


# ── Мастер добавления ───────────────────────────────────────────────────────
@router.callback_query(F.data == "acc:add")
async def acc_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddAcc.service)
    await call.message.edit_text(
        "🔐 <b>Новая учётная запись</b>\n\nШаг 1/5. <b>Сервис</b> (например, Gmail):",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(AddAcc.service)
async def acc_service(message: Message, state: FSMContext):
    await state.update_data(service=message.text.strip())
    await state.set_state(AddAcc.login)
    await message.answer("Шаг 2/5. <b>Логин</b> / email:", reply_markup=kb.cancel_only())


@router.message(AddAcc.login)
async def acc_login(message: Message, state: FSMContext):
    await state.update_data(login=message.text.strip())
    await state.set_state(AddAcc.password)
    await message.answer(
        "Шаг 3/5. <b>Пароль</b> (будет зашифрован).\n"
        "⚠️ Ваше сообщение с паролем будет автоматически удалено.\n\n"
        "Или нажмите 🎲 чтобы сгенерировать:",
        reply_markup=kb.password_gen_options(),
    )


@router.message(AddAcc.password)
async def acc_password(message: Message, state: FSMContext):
    await state.update_data(password=message.text)
    # Автоудаление сообщения с паролем
    try:
        await message.delete()
    except Exception:
        pass
    await state.set_state(AddAcc.url)
    await message.answer("✅ Пароль принят и удалён из чата.\n\n"
                         "Шаг 4/5. <b>Ссылка</b> для входа (или «-»):",
                         reply_markup=kb.cancel_only())


@router.message(AddAcc.url)
async def acc_url(message: Message, state: FSMContext):
    val = message.text.strip()
    await state.update_data(url="" if val == "-" else val)
    await state.set_state(AddAcc.note)
    await message.answer("Шаг 5/5. <b>Заметка</b> (или «-»):", reply_markup=kb.cancel_only())


@router.message(AddAcc.note)
async def acc_note(message: Message, state: FSMContext):
    val = message.text.strip()
    data = await state.get_data()
    db.add_account(
        service=data["service"],
        login=data.get("login"),
        password=data.get("password"),
        url=data.get("url", ""),
        note="" if val == "-" else val,
    )
    await state.clear()
    await message.answer(
        glados.ok("Учётная запись зашифрована и сохранена. Не благодарите."),
        reply_markup=kb.back_to_menu(),
    )
