"""
GLaDoS — общие обработчики: PIN-авторизация, главное меню, помощь,
сводка, бэкап, глобальный поиск, курсы валют.
"""

import time

from aiogram import Router, F, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, TelegramObject, FSInputFile

import glados
import keyboards as kb
import database as db
from utils import get_usdt_rates
from config import OWNER_ID, SUBSCRIPTION_WARN_DAYS, PIN_CODE, PIN_TIMEOUT_MIN, DB_PATH

router = Router()

# ── PIN-сессии ──────────────────────────────────────────────────────────────
_pin_sessions: dict[int, float] = {}   # user_id → timestamp
_pin_pending: set[int] = set()         # ожидают ввода PIN


class AuthMiddleware(BaseMiddleware):
    """Авторизация: только владелец. При включённом PIN — проверка сессии."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        # 1. Проверка владельца
        if user.id != OWNER_ID:
            if isinstance(event, Message):
                await event.answer(glados.intruder())
            elif isinstance(event, CallbackQuery):
                await event.answer(glados.intruder(), show_alert=True)
            return

        # 2. PIN-авторизация (если включена)
        if not PIN_CODE:
            return await handler(event, data)

        now = time.time()
        timeout = PIN_TIMEOUT_MIN * 60

        # Ввод PIN
        if user.id in _pin_pending:
            if isinstance(event, Message) and event.text:
                if event.text.strip() == PIN_CODE:
                    _pin_pending.discard(user.id)
                    _pin_sessions[user.id] = now
                    try:
                        await event.delete()   # удаляем сообщение с PIN
                    except Exception:
                        pass
                    await event.answer("🔓 Сессия подтверждена. Добро пожаловать.")
                    await event.answer(MENU_TEXT, reply_markup=kb.main_menu())
                else:
                    await event.answer("❌ Неверный PIN. Попробуйте ещё раз.")
                return
            if isinstance(event, CallbackQuery):
                await event.answer("Сначала введите PIN-код в чат.", show_alert=True)
                return
            return

        # Проверка сессии
        last = _pin_sessions.get(user.id, 0)
        if now - last > timeout:
            _pin_pending.add(user.id)
            if isinstance(event, Message):
                await event.answer("🔐 Сессия истекла. Введите PIN-код:")
            elif isinstance(event, CallbackQuery):
                await event.answer("Сессия истекла.", show_alert=True)
                await event.message.answer("🔐 Введите PIN-код:")
            return

        _pin_sessions[user.id] = now
        return await handler(event, data)


MENU_TEXT = (
    "<b>GLaDoS</b> · центр управления\n\n"
    "Все ваши данные под моим наблюдением. Выберите раздел. "
    "Постарайтесь не нажимать наугад — хотя кого я обманываю."
)


async def show_menu(target: Message | CallbackQuery):
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(MENU_TEXT, reply_markup=kb.main_menu())
        except Exception:
            await target.message.answer(MENU_TEXT, reply_markup=kb.main_menu())
        await target.answer()
    else:
        await target.answer(MENU_TEXT, reply_markup=kb.main_menu())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await show_menu(message)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(glados.cancelled(), reply_markup=kb.main_menu())


@router.callback_query(F.data == "menu:main")
async def cb_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_menu(call)


@router.callback_query(F.data == "menu:cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(glados.cancelled(), reply_markup=kb.back_to_menu())
    await call.answer()


# ── Помощь ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "help:show")
async def cb_help(call: CallbackQuery):
    text = (
        "<b>Инструкция по эксплуатации</b>\n\n"
        "💰 <b>Платежи</b> — журнал оплат (USDT TRC20), проверка хеша в сети TRON, "
        "экспорт в CSV.\n"
        "📅 <b>Подписки</b> — сроки, статус, автопредупреждения за "
        f"{SUBSCRIPTION_WARN_DAYS} дн., быстрое продление.\n"
        "🔐 <b>Учётные записи</b> — логины/пароли (зашифрованы), "
        "встроенный генератор паролей.\n"
        "📁 <b>Файлы</b> — загрузка и хранение документов/фото.\n"
        "🤖 <b>Боты</b> — статус (getMe), отправка сообщений, автомониторинг.\n"
        "⚙️ <b>Службы</b> — реестр интеграций и API-ключей.\n"
        "🔍 <b>Поиск</b> — поиск по всем разделам одним запросом.\n"
        "💱 <b>Курсы</b> — USDT → USD / RUB / EUR в реальном времени.\n"
        "💾 <b>Бэкап</b> — получить файл базы данных прямо в чат.\n"
        "🔐 <b>PIN</b> — защита сессии (настраивается в конфиге).\n\n"
        "Команды: /menu — меню, /cancel — отменить ввод.\n\n"
        "Ничего сложного. Даже для человека."
    )
    await call.message.edit_text(text, reply_markup=kb.back_to_menu())
    await call.answer()


# ── Сводка ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "stat:show")
async def cb_stats(call: CallbackQuery):
    pays = db.list_payments(limit=10000)
    subs = db.list_subscriptions()
    active = [s for s in subs if s["status"] == "active"]
    due = db.subscriptions_due(SUBSCRIPTION_WARN_DAYS)
    accounts = db.list_accounts()
    files = db.list_files()
    bots = db.list_bots()
    services = db.list_services()
    totals = db.payments_total()
    totals_str = ", ".join(f"{v:g} {k}" for k, v in totals.items()) or "—"

    text = (
        "<b>📊 Сводка наблюдения</b>\n\n"
        f"💰 Платежей: <b>{len(pays)}</b> (всего: {totals_str})\n"
        f"📅 Подписок: <b>{len(subs)}</b> (активных: {len(active)})\n"
        f"⏳ Истекает скоро: <b>{len(due)}</b>\n"
        f"🔐 Учётных записей: <b>{len(accounts)}</b>\n"
        f"📁 Файлов: <b>{len(files)}</b>\n"
        f"🤖 Ботов: <b>{len(bots)}</b>\n"
        f"⚙️ Служб: <b>{len(services)}</b>\n\n"
        "Статистика — единственное, чему я доверяю."
    )
    await call.message.edit_text(text, reply_markup=kb.back_to_menu())
    await call.answer()


# ── Бэкап ───────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "backup:send")
async def cb_backup(call: CallbackQuery):
    await call.answer("Подготовка бэкапа...")
    if DB_PATH.exists():
        await call.message.answer_document(
            FSInputFile(DB_PATH, filename=f"glados_backup.db"),
            caption="💾 Ваша база данных. Храните в надёжном месте. "
                    "Желательно — подальше от себя.",
        )
    else:
        await call.message.answer(glados.err("База данных не найдена."))


# ── Курсы валют ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "rates:show")
async def cb_rates(call: CallbackQuery):
    await call.answer("Запрос курсов...")
    rates = await get_usdt_rates()
    if not rates:
        await call.message.edit_text(
            glados.err("Не удалось получить курсы. CoinGecko молчит."),
            reply_markup=kb.back_to_menu(),
        )
        return
    usd = rates.get("usd", "—")
    rub = rates.get("rub", "—")
    eur = rates.get("eur", "—")
    btc = rates.get("btc", "—")
    text = (
        "<b>💱 Курсы USDT</b>\n\n"
        f"🇺🇸 USD: <b>{usd}</b>\n"
        f"🇷🇺 RUB: <b>{rub}</b>\n"
        f"🇪🇺 EUR: <b>{eur}</b>\n"
        f"₿ BTC: <code>{btc}</code>\n\n"
        "Данные CoinGecko. Обновляются в реальном времени."
    )
    await call.message.edit_text(text, reply_markup=kb.back_to_menu())


# ── Глобальный поиск ───────────────────────────────────────────────────────
class SearchState(StatesGroup):
    query = State()


@router.callback_query(F.data == "search:start")
async def search_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.query)
    await call.message.edit_text(
        "🔍 <b>Поиск</b>\n\nВведите запрос — я поищу по всем разделам:",
        reply_markup=kb.cancel_only(),
    )
    await call.answer()


@router.message(SearchState.query)
async def search_exec(message: Message, state: FSMContext):
    q = message.text.strip().lower()
    await state.clear()
    if len(q) < 2:
        return await message.answer(glados.err("Хотя бы 2 символа, пожалуйста."),
                                    reply_markup=kb.back_to_menu())
    results: list[str] = []

    # Платежи
    for r in db.list_payments(limit=500):
        fields = f"{r['name']} {r['service'] or ''} {r['tx_hash'] or ''} {r['note'] or ''}"
        if q in fields.lower():
            results.append(f"💰 Платёж: <b>{r['name']}</b> — {r['amount']:g} {r['currency']}")

    # Подписки
    for r in db.list_subscriptions():
        fields = f"{r['name']} {r['service'] or ''} {r['note'] or ''}"
        if q in fields.lower():
            results.append(f"📅 Подписка: <b>{r['name']}</b> до {r['end_date']}")

    # Учётные записи
    for r in db.list_accounts():
        fields = f"{r['service']} {r['login'] or ''}"
        if q in fields.lower():
            results.append(f"🔐 Аккаунт: <b>{r['service']}</b> ({r['login'] or '—'})")

    # Файлы
    for r in db.list_files():
        fields = f"{r['file_name']} {r['category'] or ''} {r['note'] or ''}"
        if q in fields.lower():
            results.append(f"📁 Файл: <b>{r['file_name']}</b>")

    # Боты
    for r in db.list_bots():
        fields = f"{r['name']} {r['username'] or ''} {r['note'] or ''}"
        if q in fields.lower():
            results.append(f"🤖 Бот: <b>{r['name']}</b>")

    # Службы
    for r in db.list_services():
        fields = f"{r['name']} {r['kind'] or ''} {r['note'] or ''}"
        if q in fields.lower():
            results.append(f"⚙️ Служба: <b>{r['name']}</b>")

    if not results:
        await message.answer(
            f"🔍 По запросу «{q}» ничего не найдено. Либо данных нет, "
            "либо вы ищете смысл жизни — а его тут не хранят.",
            reply_markup=kb.back_to_menu(),
        )
    else:
        text = f"🔍 Результаты по «{q}» ({len(results)}):\n\n" + "\n".join(results[:30])
        if len(results) > 30:
            text += f"\n\n…и ещё {len(results) - 30}. Уточните запрос."
        await message.answer(text, reply_markup=kb.back_to_menu())

async def show_main_menu(message):
    """Показать главное меню после авторизации."""
    await message.answer(MENU_TEXT, reply_markup=kb.main_menu())
