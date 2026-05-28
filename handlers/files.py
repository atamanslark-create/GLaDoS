"""
GLaDoS — раздел «Файлы».
Принимает документы/фото, сохраняет на диск и в базу, отдаёт обратно по запросу.
"""

import os
import time
from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile

import glados
import keyboards as kb
import database as db
from config import FILES_DIR, MAX_FILE_MB

router = Router()
SECTION = "file"


class AddFile(StatesGroup):
    upload = State()
    category = State()
    note = State()


def _human_size(n: int | None) -> str:
    if not n:
        return "—"
    units = ["Б", "КБ", "МБ", "ГБ"]
    f = float(n)
    for u in units:
        if f < 1024:
            return f"{f:.0f} {u}" if u == "Б" else f"{f:.1f} {u}"
        f /= 1024
    return f"{f:.1f} ТБ"


def _label(r) -> str:
    return f"📎 {r['file_name']} · {_human_size(r['size'])}"


async def _show_list(target: CallbackQuery):
    rows = db.list_files()
    if not rows:
        await target.message.edit_text(
            "📁 <b>Файлы</b>\n\n" + glados.empty() +
            "\n\nНажмите «Добавить» и пришлите документ или фото.",
            reply_markup=kb.section_menu(SECTION, "➕ Добавить файл"),
        )
    else:
        await target.message.edit_text(
            "📁 <b>Файлы</b>\n\nВыберите файл:",
            reply_markup=kb.list_keyboard(SECTION, rows, _label, "➕ Добавить файл"),
        )
    await target.answer()


@router.callback_query(F.data == "file:list")
async def file_list(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_list(call)


@router.callback_query(F.data.startswith("file:view:"))
async def file_view(call: CallbackQuery):
    fid = int(call.data.split(":")[2])
    r = db.get_file(fid)
    if not r:
        await call.answer("Файл пропал.", show_alert=True)
        return await _show_list(call)
    text = (
        f"📎 <b>{r['file_name']}</b>\n\n"
        f"Категория: {r['category'] or '—'}\n"
        f"Размер: {_human_size(r['size'])}\n"
        f"Заметка: {r['note'] or '—'}\n"
        f"Сохранён: {r['created_at']}"
    )
    extra = [("⬇️ Получить файл", f"file:get:{fid}")]
    await call.message.edit_text(text, reply_markup=kb.item_actions(SECTION, fid, extra))
    await call.answer()


@router.callback_query(F.data.startswith("file:get:"))
async def file_get(call: CallbackQuery):
    fid = int(call.data.split(":")[2])
    r = db.get_file(fid)
    if not r:
        return await call.answer("Файл пропал.", show_alert=True)
    await call.answer("Отправляю...")
    # Сначала пробуем по сохранённому file_id (быстро), иначе с диска.
    try:
        if r["tg_file_id"]:
            await call.message.answer_document(r["tg_file_id"], caption=r["file_name"])
            return
    except Exception:
        pass
    path = Path(r["stored_path"])
    if path.exists():
        await call.message.answer_document(FSInputFile(path), caption=r["file_name"])
    else:
        await call.message.answer(glados.err("Файл не найден ни в Telegram, ни на диске."))


@router.callback_query(F.data.startswith("file:del:"))
async def file_del(call: CallbackQuery):
    fid = int(call.data.split(":")[2])
    await call.message.edit_text(
        "Удалить файл (и с диска тоже)?",
        reply_markup=kb.confirm_delete(SECTION, fid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("file:delyes:"))
async def file_delyes(call: CallbackQuery):
    fid = int(call.data.split(":")[2])
    r = db.get_file(fid)
    if r:
        try:
            p = Path(r["stored_path"])
            if p.exists():
                p.unlink()
        except OSError:
            pass
    db.delete_file(fid)
    await call.answer("Уничтожено.")
    await _show_list(call)


# --- Мастер добавления ------------------------------------------------------
@router.callback_query(F.data == "file:add")
async def file_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddFile.upload)
    await call.message.edit_text(
        "📁 <b>Новый файл</b>\n\nПришлите <b>документ</b> или <b>фото</b> "
        "(до "
        f"{MAX_FILE_MB} МБ):",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(AddFile.upload, F.document | F.photo)
async def file_receive(message: Message, state: FSMContext):
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or f"document_{int(time.time())}"
        size = message.document.file_size
    else:  # photo
        photo = message.photo[-1]
        file_id = photo.file_id
        file_name = f"photo_{int(time.time())}.jpg"
        size = photo.file_size

    if size and size > MAX_FILE_MB * 1024 * 1024:
        return await message.answer(glados.err(f"Слишком большой файл (> {MAX_FILE_MB} МБ)."))

    # Уникальное имя на диске
    safe = "".join(ch for ch in file_name if ch.isalnum() or ch in (" ", ".", "_", "-")).strip()
    stored = FILES_DIR / f"{int(time.time())}_{safe}"
    try:
        tg_file = await message.bot.get_file(file_id)
        await message.bot.download_file(tg_file.file_path, destination=stored)
        size = size or (stored.stat().st_size if stored.exists() else None)
    except Exception as e:
        return await message.answer(glados.err(f"Не удалось скачать файл: {e}"))

    await state.update_data(file_name=file_name, stored_path=str(stored),
                            tg_file_id=file_id, size=size)
    await state.set_state(AddFile.category)
    await message.answer(
        f"Принято: <b>{file_name}</b> ({_human_size(size)}).\n"
        "Укажите <b>категорию</b> (или «-»):",
        reply_markup=kb.cancel_only(),
    )


@router.message(AddFile.upload)
async def file_wrong(message: Message):
    await message.answer("Мне нужен документ или фото, а не это. Попробуйте ещё раз.")


@router.message(AddFile.category)
async def file_category(message: Message, state: FSMContext):
    val = message.text.strip()
    await state.update_data(category=None if val == "-" else val)
    await state.set_state(AddFile.note)
    await message.answer("<b>Заметка</b> к файлу (или «-»):", reply_markup=kb.cancel_only())


@router.message(AddFile.note)
async def file_note(message: Message, state: FSMContext):
    val = message.text.strip()
    data = await state.get_data()
    db.add_file(
        file_name=data["file_name"],
        stored_path=data["stored_path"],
        tg_file_id=data.get("tg_file_id"),
        category=data.get("category"),
        size=data.get("size"),
        note="" if val == "-" else val,
    )
    await state.clear()
    await message.answer(glados.ok("Файл архивирован. В надёжном месте. В отличие от ваших."),
                         reply_markup=kb.back_to_menu())
