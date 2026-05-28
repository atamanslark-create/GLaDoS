"""
GLaDoS — Интеграция с Ollama LLM.
Анализ серверов через локальную языковую модель.
"""

import json
import logging
import aiohttp
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db

log = logging.getLogger("GLaDoS.llm")
router = Router()

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"

class LLMState(StatesGroup):
    waiting_question = State()

async def _ask_ollama(question: str, context: str = "", model: str = OLLAMA_MODEL) -> str:
    system_prompt = """Ты — системный администратор GLaDoS, помощник по мониторингу серверов.
Отвечай кратко и по делу. Используй технический язык. Отвечай на русском языке."""

    if context:
        system_prompt += f"\n\nТекущие данные серверов:\n{context}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "stream": False
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("message", {}).get("content", "Нет ответа")
                else:
                    return f"Ошибка Ollama: HTTP {resp.status}"
    except aiohttp.ClientConnectorError:
        return "❌ Ollama недоступна. Запустите: `ollama serve`"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def _collect_server_context() -> str:
    bots = db.list_bots()
    if not bots:
        return "Нет зарегистрированных серверов."

    lines = []
    for bot in bots:
        bot_d = dict(bot)
        status = bot_d.get("status") or "unknown"
        lines.append(f"Сервер: {bot_d['name']} | Статус: {status}")

        latest = db.get_latest_report(bot_d["id"])
        if latest:
            try:
                details = latest["details"] if latest["details"] is not None else "{}"
                if isinstance(details, str):
                    details = json.loads(details)
                if details:
                    cpu = details.get("cpu_percent", "?")
                    ram = details.get("memory_percent", "?")
                    lines.append(f"  CPU: {cpu}%, RAM: {ram}%")
            except:
                pass

    return "\n".join(lines)

def _build_llm_menu() -> object:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Анализ нагрузки", callback_data="llm:quick:cpu")
    kb.button(text="⚠️ Проблемы", callback_data="llm:quick:issues")
    kb.button(text="✏️ Свой вопрос", callback_data="llm:custom")
    kb.button(text="← Меню", callback_data="menu:main")
    kb.adjust(2, 2)
    return kb.as_markup()

@router.callback_query(F.data == "llm:show")
async def show_llm_menu(call: CallbackQuery):
    text = "🤖 *AI-анализ серверов*\n\nВыберите вопрос или задайте свой:"
    await call.message.edit_text(
        text,
        reply_markup=_build_llm_menu(),
        parse_mode="Markdown"
    )
    await call.answer()

@router.callback_query(F.data == "llm:quick:cpu")
async def llm_cpu_analysis(call: CallbackQuery):
    await call.message.edit_text("🤖 *Анализирую нагрузку...*", parse_mode="Markdown")
    context = _collect_server_context()
    answer = await _ask_ollama("Проанализируй текущую нагрузку всех серверов и дай рекомендации", context)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="← Назад", callback_data="llm:show")
    kb.adjust(1)
    
    text = f"🤖 *AI-ответ*\n\n{answer}"[:4000]
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "llm:quick:issues")
async def llm_issues_analysis(call: CallbackQuery):
    await call.message.edit_text("🤖 *Ищу проблемы...*", parse_mode="Markdown")
    context = _collect_server_context()
    answer = await _ask_ollama("Какие проблемы есть на серверах? Укажи конкретные сервера.", context)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="← Назад", callback_data="llm:show")
    kb.adjust(1)
    
    text = f"🤖 *AI-ответ*\n\n{answer}"[:4000]
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "llm:custom")
async def llm_custom_question(call: CallbackQuery, state: FSMContext):
    await state.set_state(LLMState.waiting_question)
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="llm:show")
    await call.message.edit_text(
        "🤖 *Задайте вопрос*\n\nНапример: Почему nginx потребляет много памяти?",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )

@router.message(LLMState.waiting_question)
async def llm_process_question(message: Message, state: FSMContext):
    question = message.text.strip()
    await state.clear()
    try:
        await message.delete()
    except:
        pass

    thinking_msg = await message.answer(f"🤖 *Думаю...*\n\n_{question}_", parse_mode="Markdown")
    context = _collect_server_context()
    answer = await _ask_ollama(question, context)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="← Назад", callback_data="llm:show")
    kb.adjust(1)
    
    text = f"🤖 *AI-ответ*\n\n{answer}"[:4000]
    await thinking_msg.edit_text(text, reply_markup=kb.as_markup(), parse_mode="Markdown")