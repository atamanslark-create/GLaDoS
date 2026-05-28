"""
GLaDoS — раздел «Платежи».
Журнал оплат: USDT TRC20, проверка хеша в сети TRON, экспорт CSV.
"""

import csv
import io
import tempfile
from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import glados
import keyboards as kb
import database as db
from utils import check_tron_tx

router = Router()
SECTION = "pay"


class AddPayment(StatesGroup):
    name = State()
    service = State()
    amount = State()
    tx_hash = State()
    note = State()


def _label(r) -> str:
    amt = f"{r['amount']:g} {r['currency']}" if r["amount"] is not None else "—"
    return f"💸 {r['name']} · {amt}"


async def _show_list(target: CallbackQuery):
    rows = db.list_payments()
    extra = [("📥 Экспорт CSV", "pay:csv")] if rows else None
    if not rows:
        await target.message.edit_text(
            "💰 <b>Журнал оплат</b>\n\n" + glados.empty(),
            reply_markup=kb.section_menu(SECTION, "➕ Добавить платёж"),
        )
    else:
        await target.message.edit_text(
            "💰 <b>Журнал оплат</b>\n\nВыберите запись для деталей:",
            reply_markup=kb.list_keyboard(SECTION, rows, _label,
                                          "➕ Добавить платёж", extra),
        )
    await target.answer()


@router.callback_query(F.data == "pay:list")
async def pay_list(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_list(call)


@router.callback_query(F.data.startswith("pay:view:"))
async def pay_view(call: CallbackQuery):
    pid = int(call.data.split(":")[2])
    r = db.get_payment(pid)
    if not r:
        await call.answer("Запись испарилась.", show_alert=True)
        return await _show_list(call)
    amt = f"{r['amount']:g} {r['currency']} ({r['network']})" if r["amount"] is not None else "—"
    text = (
        f"💸 <b>{r['name']}</b>\n\n"
        f"Сервис: {r['service'] or '—'}\n"
        f"Сумма: {amt}\n"
        f"Хеш: <code>{r['tx_hash'] or '—'}</code>\n"
        f"Заметка: {r['note'] or '—'}\n"
        f"Добавлено: {r['created_at']}"
    )
    extra = []
    if r["tx_hash"]:
        extra.append(("🔎 Проверить в TRON", f"pay:tron:{pid}"))
    await call.message.edit_text(text, reply_markup=kb.item_actions(SECTION, pid, extra))
    await call.answer()


# ── Проверка транзакции в сети TRON ─────────────────────────────────────────
@router.callback_query(F.data.startswith("pay:tron:"))
async def pay_tron(call: CallbackQuery):
    pid = int(call.data.split(":")[2])
    r = db.get_payment(pid)
    if not r or not r["tx_hash"]:
        return await call.answer("Нет хеша для проверки.", show_alert=True)
    await call.answer("Запрос к TronGrid...")
    result = await check_tron_tx(r["tx_hash"])
    if not result:
        await call.message.answer(glados.err("Нет ответа от сети TRON."))
        return
    if "error" in result:
        await call.message.answer(
            glados.err(f"Ошибка: <code>{result['error']}</code>"))
        return
    status = "✅ подтверждена" if result.get("confirmed") else "❌ не подтверждена"
    lines = [f"🔎 <b>Проверка транзакции</b>\n\nСтатус: {status}"]
    if result.get("status"):
        lines.append(f"Contract: {result['status']}")
    for ev in result.get("events", []):
        if ev.get("type") == "USDT TRC20":
            lines.append(
                f"\n💵 <b>{ev['amount']} USDT</b>\n"
                f"От: <code>{ev['from']}</code>\n"
                f"Кому: <code>{ev['to']}</code>"
            )
        else:
            lines.append(f"Event: {ev.get('type')}")
    await call.message.answer("\n".join(lines), reply_markup=kb.back_to_menu())


# ── Экспорт CSV ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "pay:csv")
async def pay_csv(call: CallbackQuery):
    rows = db.list_payments(limit=50000)
    if not rows:
        return await call.answer("Нечего экспортировать.", show_alert=True)
    await call.answer("Формирую CSV...")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Название", "Сервис", "Сумма", "Валюта",
                     "Сеть", "Хеш", "Заметка", "Дата"])
    for r in rows:
        writer.writerow([r["id"], r["name"], r["service"] or "",
                         r["amount"], r["currency"], r["network"],
                         r["tx_hash"] or "", r["note"] or "", r["created_at"]])
    raw = buf.getvalue().encode("utf-8-sig")  # BOM для Excel
    doc = BufferedInputFile(raw, filename="payments_export.csv")
    await call.message.answer_document(doc, caption="📥 Экспорт журнала оплат.")


@router.callback_query(F.data.startswith("pay:del:"))
async def pay_del(call: CallbackQuery):
    pid = int(call.data.split(":")[2])
    await call.message.edit_text(
        "Удалить эту запись о платеже? Назад дороги не будет.",
        reply_markup=kb.confirm_delete(SECTION, pid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pay:delyes:"))
async def pay_delyes(call: CallbackQuery):
    pid = int(call.data.split(":")[2])
    db.delete_payment(pid)
    await call.answer("Стёрто из истории.")
    await _show_list(call)


# ── Мастер добавления ───────────────────────────────────────────────────────
@router.callback_query(F.data == "pay:add")
async def pay_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddPayment.name)
    await call.message.edit_text(
        "💰 <b>Новый платёж</b>\n\nШаг 1/5. Введите <b>наименование</b> платежа:",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(AddPayment.name)
async def pay_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddPayment.service)
    await message.answer("Шаг 2/5. Какой <b>сервис</b>? (или «-» чтобы пропустить)",
                         reply_markup=kb.cancel_only())


@router.message(AddPayment.service)
async def pay_service(message: Message, state: FSMContext):
    val = message.text.strip()
    await state.update_data(service=None if val == "-" else val)
    await state.set_state(AddPayment.amount)
    await message.answer("Шаг 3/5. <b>Сумма</b> (число, в USDT). Например 19.99:",
                         reply_markup=kb.cancel_only())


@router.message(AddPayment.amount)
async def pay_amount(message: Message, state: FSMContext):
    raw = message.text.strip().replace(",", ".").replace(" ", "")
    try:
        amount = float(raw)
    except ValueError:
        return await message.answer(glados.err("Нужно число. Например: 19.99"))
    await state.update_data(amount=amount)
    await state.set_state(AddPayment.tx_hash)
    await message.answer(
        "Шаг 4/5. <b>Хеш транзакции</b> USDT TRC20 (или «-»):",
        reply_markup=kb.cancel_only(),
    )


@router.message(AddPayment.tx_hash)
async def pay_hash(message: Message, state: FSMContext):
    val = message.text.strip()
    await state.update_data(tx_hash=None if val == "-" else val)
    await state.set_state(AddPayment.note)
    await message.answer("Шаг 5/5. <b>Заметка</b> (или «-»):", reply_markup=kb.cancel_only())


@router.message(AddPayment.note)
async def pay_note(message: Message, state: FSMContext):
    val = message.text.strip()
    data = await state.get_data()
    db.add_payment(
        name=data["name"],
        service=data.get("service"),
        amount=data.get("amount"),
        tx_hash=data.get("tx_hash"),
        note="" if val == "-" else val,
    )
    await state.clear()
    await message.answer(glados.ok("Платёж занесён в журнал."), reply_markup=kb.back_to_menu())
