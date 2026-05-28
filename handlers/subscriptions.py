"""
GLaDoS — раздел «Подписки».
Статус, срок действия, предупреждения, быстрое продление.
"""

from datetime import date, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import glados
import keyboards as kb
import database as db

router = Router()
SECTION = "sub"


class AddSub(StatesGroup):
    name = State()
    service = State()
    amount = State()
    period = State()
    end_date = State()
    note = State()


def _days_left(end_iso: str) -> int | None:
    try:
        return (date.fromisoformat(end_iso) - date.today()).days
    except (ValueError, TypeError):
        return None


def _status_icon(r) -> str:
    if r["status"] != "active":
        return "⛔"
    d = _days_left(r["end_date"])
    if d is None:
        return "❔"
    if d < 0:
        return "❌"
    if d <= 5:
        return "⚠️"
    return "✅"


def _label(r) -> str:
    d = _days_left(r["end_date"])
    tail = f"{d} дн." if d is not None and d >= 0 else "истекла"
    return f"{_status_icon(r)} {r['name']} · {tail}"


async def _show_list(target: CallbackQuery):
    rows = db.list_subscriptions()
    if not rows:
        await target.message.edit_text(
            "📅 <b>Подписки</b>\n\n" + glados.empty(),
            reply_markup=kb.section_menu(SECTION, "➕ Добавить подписку"),
        )
    else:
        await target.message.edit_text(
            "📅 <b>Подписки</b>\n\n"
            "✅ активна · ⚠️ скоро истекает · ❌ истекла · ⛔ отменена\n\n"
            "Выберите подписку:",
            reply_markup=kb.list_keyboard(SECTION, rows, _label, "➕ Добавить подписку"),
        )
    await target.answer()


@router.callback_query(F.data == "sub:list")
async def sub_list(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_list(call)



async def _show_sub(message, sid: int):
    """Render subscription card (reusable from multiple handlers)."""
    r = db.get_subscription(sid)
    if not r:
        return
    d = _days_left(r["end_date"])
    if d is None:
        left = "—"
    elif d < 0:
        left = f"истекла {abs(d)} дн. назад"
    else:
        left = f"осталось {d} дн."
    amt = f"{r['amount']:g} {r['currency']}" if r["amount"] is not None else "—"
    text = (
        f"{_status_icon(r)} <b>{r['name']}</b>\n\n"
        f"Сервис: {r['service'] or '—'}\n"
        f"Стоимость: {amt} / {r['period'] or '—'}\n"
        f"Действует до: <b>{r['end_date']}</b> ({left})\n"
        f"Статус: {r['status']}\n"
        f"Заметка: {r['note'] or '—'}"
    )
    extra = []
    if r["status"] == "active":
        extra.append(("🔄 Продлить", f"sub:renewmenu:{sid}"))
        extra.append(("⛔ Отменить", f"sub:cancel:{sid}"))
    else:
        extra.append(("✅ Активировать", f"sub:activate:{sid}"))
        extra.append(("🔄 Продлить", f"sub:renewmenu:{sid}"))
    try:
        await message.edit_text(text, reply_markup=kb.item_actions(SECTION, sid, extra))
    except Exception:
        await message.answer(text, reply_markup=kb.item_actions(SECTION, sid, extra))


@router.callback_query(F.data.startswith("sub:view:"))
async def sub_view(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    r = db.get_subscription(sid)
    if not r:
        await call.answer("Запись исчезла.", show_alert=True)
        return await _show_list(call)
    await _show_sub(call.message, sid)
    await call.answer()


# ── Продление подписки ──────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("sub:renewmenu:"))
async def sub_renew_menu(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    r = db.get_subscription(sid)
    if not r:
        return await call.answer("Нет такой подписки.", show_alert=True)
    await call.message.edit_text(
        f"🔄 <b>Продление: {r['name']}</b>\n\n"
        f"Текущий срок: до {r['end_date']}\n\n"
        "На сколько продлить?",
        reply_markup=kb.renew_period_choice(sid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("sub:renew:"))
async def sub_renew(call: CallbackQuery):
    parts = call.data.split(":")
    sid = int(parts[2])
    days = int(parts[3])
    r = db.get_subscription(sid)
    if not r:
        return await call.answer("Нет такой подписки.", show_alert=True)
    try:
        current_end = date.fromisoformat(r["end_date"])
    except (ValueError, TypeError):
        current_end = date.today()
    # Если уже истекла — считаем от сегодня
    base = max(current_end, date.today())
    new_end = base + timedelta(days=days)
    db.update_subscription_end(sid, new_end.isoformat())
    db.set_subscription_status(sid, "active")
    await call.answer(f"Продлена до {new_end.isoformat()}")
    await _show_sub(call.message, sid)


@router.callback_query(F.data.startswith("sub:cancel:"))
async def sub_cancel(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    db.set_subscription_status(sid, "cancelled")
    await call.answer("Подписка помечена как отменённой.")
    await _show_sub(call.message, sid)


@router.callback_query(F.data.startswith("sub:activate:"))
async def sub_activate(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    db.set_subscription_status(sid, "active")
    await call.answer("Снова активна.")
    await _show_sub(call.message, sid)


@router.callback_query(F.data.startswith("sub:del:"))
async def sub_del(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    await call.message.edit_text(
        "Удалить эту подписку навсегда?",
        reply_markup=kb.confirm_delete(SECTION, sid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("sub:delyes:"))
async def sub_delyes(call: CallbackQuery):
    sid = int(call.data.split(":")[2])
    db.delete_subscription(sid)
    await call.answer("Удалено.")
    await _show_list(call)


# ── Мастер добавления ───────────────────────────────────────────────────────
@router.callback_query(F.data == "sub:add")
async def sub_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddSub.name)
    await call.message.edit_text(
        "📅 <b>Новая подписка</b>\n\nШаг 1/6. <b>Название</b> подписки:",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(AddSub.name)
async def sub_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddSub.service)
    await message.answer("Шаг 2/6. <b>Сервис</b> (или «-»):", reply_markup=kb.cancel_only())


@router.message(AddSub.service)
async def sub_service(message: Message, state: FSMContext):
    val = message.text.strip()
    await state.update_data(service=None if val == "-" else val)
    await state.set_state(AddSub.amount)
    await message.answer("Шаг 3/6. <b>Стоимость</b> в USDT (или «-»):",
                         reply_markup=kb.cancel_only())


@router.message(AddSub.amount)
async def sub_amount(message: Message, state: FSMContext):
    raw = message.text.strip().replace(",", ".").replace(" ", "")
    if raw == "-":
        amount = None
    else:
        try:
            amount = float(raw)
        except ValueError:
            return await message.answer(glados.err("Число или «-»."))
    await state.update_data(amount=amount)
    await state.set_state(AddSub.period)
    await message.answer("Шаг 4/6. Выберите <b>период</b>:", reply_markup=kb.period_choice())


@router.callback_query(AddSub.period, F.data.startswith("form:period:"))
async def sub_period(call: CallbackQuery, state: FSMContext):
    period = call.data.split(":", 2)[2]
    await state.update_data(period=period)
    await state.set_state(AddSub.end_date)
    await call.message.edit_text(
        "Шаг 5/6. <b>Дата окончания</b> — ГГГГ-ММ-ДД (например 2026-12-31):",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(AddSub.end_date)
async def sub_end(message: Message, state: FSMContext):
    raw = message.text.strip()
    try:
        date.fromisoformat(raw)
    except ValueError:
        return await message.answer(glados.err("Формат даты: ГГГГ-ММ-ДД"))
    await state.update_data(end_date=raw)
    await state.set_state(AddSub.note)
    await message.answer("Шаг 6/6. <b>Заметка</b> (или «-»):", reply_markup=kb.cancel_only())


@router.message(AddSub.note)
async def sub_note(message: Message, state: FSMContext):
    val = message.text.strip()
    data = await state.get_data()
    db.add_subscription(
        name=data["name"],
        service=data.get("service"),
        amount=data.get("amount"),
        period=data.get("period"),
        end_date=data["end_date"],
        note="" if val == "-" else val,
    )
    await state.clear()
    await message.answer(
        glados.ok("Подписка под наблюдением. Я предупрежу вас об окончании. Возможно."),
        reply_markup=kb.back_to_menu(),
    )
