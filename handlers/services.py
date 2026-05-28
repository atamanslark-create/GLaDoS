"""
GLaDoS — раздел «Службы».
Реестр подключаемых функций/интеграций. Каждая служба имеет тип и
зашифрованную конфигурацию (например, API-ключ). Можно включать/выключать.
Это каркас для расширения: сюда вы будете добавлять новые возможности бота.
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import glados
import keyboards as kb
import database as db

router = Router()
SECTION = "srv"


class AddSrv(StatesGroup):
    name = State()
    kind = State()
    config = State()
    note = State()


def _label(r) -> str:
    return f"{'🟢' if r['enabled'] else '⚪'} {r['name']} ({r['kind'] or '—'})"


async def _show_list(target: CallbackQuery):
    rows = db.list_services()
    if not rows:
        await target.message.edit_text(
            "⚙️ <b>Службы и функции</b>\n\n" + glados.empty() +
            "\n\nЗдесь вы подключаете новые возможности: API-ключи, интеграции, "
            "внешние сервисы.",
            reply_markup=kb.section_menu(SECTION, "➕ Подключить службу"),
        )
    else:
        await target.message.edit_text(
            "⚙️ <b>Службы и функции</b>\n\n🟢 включена · ⚪ выключена\n\nВыберите службу:",
            reply_markup=kb.list_keyboard(SECTION, rows, _label, "➕ Подключить службу"),
        )
    await target.answer()


@router.callback_query(F.data == "srv:list")
async def srv_list(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_list(call)


async def _show_srv(message, sid: int):
    s = db.get_service(sid)
    if not s:
        return
    cfg = s["config"] or "—"
    text = (
        f"⚙️ <b>{s['name']}</b>\n\n"
        f"Тип: {s['kind'] or '—'}\n"
        f"Состояние: {'включена 🟢' if s['enabled'] else 'выключена ⚪'}\n"
        f"Конфигурация: <code>{cfg}</code>\n"
        f"Заметка: {s['note'] or '—'}\n"
        f"Добавлена: {s['created_at']}"
    )
    toggle_label = "⚪ Выключить" if s["enabled"] else "🟢 Включить"
    extra = [(toggle_label, f"srv:toggle:{sid}")]
    try:
        await message.edit_text(text, reply_markup=kb.item_actions(SECTION, sid, extra))
    except Exception:
        await message.answer(text, reply_markup=kb.item_actions(SECTION, sid, extra))


@router.callback_query(F.data.startswith("srv:view:"))
async def srv_view(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    s = db.get_service(sid)
    if not s:
        await call.answer("Служба исчезла.", show_alert=True)
        return await _show_list(call)
    await _show_srv(call.message, sid)
    await call.answer()


@router.callback_query(F.data.startswith("srv:toggle:"))
async def srv_toggle(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    db.toggle_service(sid)
    await call.answer("Состояние изменено.")
    await _show_srv(call.message, sid)


@router.callback_query(F.data.startswith("srv:del:"))
async def srv_del(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    await call.message.edit_text(
        "Отключить и удалить эту службу?",
        reply_markup=kb.confirm_delete(SECTION, sid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("srv:delyes:"))
async def srv_delyes(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    db.delete_service(sid)
    await call.answer("Служба демонтирована.")
    await _show_list(call)


# --- Мастер добавления ------------------------------------------------------
@router.callback_query(F.data == "srv:add")
async def srv_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddSrv.name)
    await call.message.edit_text(
        "⚙️ <b>Новая служба</b>\n\nШаг 1/4. <b>Название</b> службы:",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(AddSrv.name)
async def srv_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddSrv.kind)
    await message.answer(
        "Шаг 2/4. <b>Тип</b> (например: API, webhook, уведомления, парсер):",
        reply_markup=kb.cancel_only(),
    )


@router.message(AddSrv.kind)
async def srv_kind(message: Message, state: FSMContext):
    await state.update_data(kind=message.text.strip())
    await state.set_state(AddSrv.config)
    await message.answer(
        "Шаг 3/4. <b>Конфигурация</b> — ключ, токен или JSON (или «-»). "
        "Будет зашифрована:",
        reply_markup=kb.cancel_only(),
    )


@router.message(AddSrv.config)
async def srv_config(message: Message, state: FSMContext):
    val = message.text.strip()
    await state.update_data(config="" if val == "-" else val)
    await state.set_state(AddSrv.note)
    await message.answer("Шаг 4/4. <b>Заметка</b> (или «-»):", reply_markup=kb.cancel_only())


@router.message(AddSrv.note)
async def srv_note(message: Message, state: FSMContext):
    val = message.text.strip()
    data = await state.get_data()
    db.add_service(
        name=data["name"],
        kind=data.get("kind"),
        config=data.get("config", ""),
        note="" if val == "-" else val,
    )
    await state.clear()
    await message.answer(
        glados.ok("Служба подключена и активна. Возможности расширяются. Тревожно, не правда ли?"),
        reply_markup=kb.back_to_menu(),
    )
