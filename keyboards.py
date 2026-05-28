"""
GLaDoS — клавиатуры (кнопочный интерфейс).
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    """Главное меню GLaDoS."""
    kb = InlineKeyboardBuilder()
    buttons = [
        ("🤖 Боты",          "bot:list"),
        ("🗺️ Карта серверов", "server_map:show"),
        ("📋 История событий","events:show"),
        ("📊 Отчёты",        "reports:list"),
        ("⚙️ Команды",       "commands:list"),
        ("🤖 AI-анализ",     "llm:show"),
        ("💳 Платежи",       "pay:list"),
        ("📦 Сервисы",       "srv:list"),
        ("👤 Аккаунты",      "acc:list"),
        ("📁 Файлы",         "file:list"),
    ]
    for text, cb in buttons:
        kb.button(text=text, callback_data=cb)
    kb.adjust(2)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="← Главное меню", callback_data="menu:main")
    return kb.as_markup()


def section_menu(section: str, add_label: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=add_label, callback_data=f"{section}:add")
    kb.button(text="🔄 Обновить", callback_data=f"{section}:list")
    kb.button(text="‹ Главное меню", callback_data="menu:main")
    kb.adjust(1, 2)
    return kb.as_markup()


def list_keyboard(section: str, rows, label_fn, add_label: str,
                  extra_buttons: list[tuple[str, str]] | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in rows:
        kb.button(text=label_fn(r), callback_data=f"{section}:view:{r['id']}")
    kb.adjust(1)
    tail = InlineKeyboardBuilder()
    if extra_buttons:
        for text, cb in extra_buttons:
            tail.button(text=text, callback_data=cb)
    tail.button(text=add_label, callback_data=f"{section}:add")
    tail.button(text="‹ Главное меню", callback_data="menu:main")
    tail.adjust(2)
    kb.attach(tail)
    return kb.as_markup()


def item_actions(section: str, item_id: int,
                 extra: list[tuple[str, str]] | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if extra:
        for text, cb in extra:
            kb.button(text=text, callback_data=cb)
    kb.button(text="🗑 Удалить", callback_data=f"{section}:del:{item_id}")
    kb.button(text="‹ К списку", callback_data=f"{section}:list")
    kb.adjust(1)
    return kb.as_markup()


def confirm_delete(section: str, item_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Да, удалить", callback_data=f"{section}:delyes:{item_id}")
    kb.button(text="‹ Отмена", callback_data=f"{section}:view:{item_id}")
    kb.adjust(2)
    return kb.as_markup()


def cancel_only() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Отмена", callback_data="menu:cancel")
    return kb.as_markup()


def skip_or_cancel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Пропустить", callback_data="form:skip")
    kb.button(text="✖️ Отмена", callback_data="menu:cancel")
    kb.adjust(2)
    return kb.as_markup()


def period_choice() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for label, val in [("Месяц", "месяц"), ("3 месяца", "3 месяца"),
                       ("6 месяцев", "6 месяцев"), ("Год", "год")]:
        kb.button(text=label, callback_data=f"form:period:{val}")
    kb.button(text="✖️ Отмена", callback_data="menu:cancel")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def password_gen_options() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="16 символов", callback_data="pwgen:16:1")
    kb.button(text="20 символов", callback_data="pwgen:20:1")
    kb.button(text="24 символа", callback_data="pwgen:24:1")
    kb.button(text="32 символа", callback_data="pwgen:32:1")
    kb.button(text="20 (без спец.)", callback_data="pwgen:20:0")
    kb.button(text="✖️ Отмена", callback_data="menu:cancel")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def renew_period_choice(sid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for label, days in [("+ Месяц", 30), ("+ 3 мес.", 90),
                        ("+ 6 мес.", 180), ("+ Год", 365)]:
        kb.button(text=label, callback_data=f"sub:renew:{sid}:{days}")
    kb.button(text="‹ Назад", callback_data=f"sub:view:{sid}")
    kb.adjust(2, 2, 1)
    return kb.as_markup()

def inline_buttons(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Создать клавиатуру из списка кнопок [(text, callback_data), ...]"""
    kb = InlineKeyboardBuilder()
    for text, callback_data in buttons:
        kb.button(text=text, callback_data=callback_data)
    kb.adjust(2)
    return kb.as_markup()