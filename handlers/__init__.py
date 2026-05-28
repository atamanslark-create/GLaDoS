"""Сборка всех маршрутизаторов разделов."""

from .common import router as common_router, AuthMiddleware
from .payments import router as payments_router
from .subscriptions import router as subscriptions_router
from .accounts import router as accounts_router
from .files import router as files_router
from .bots import router as bots_router
from .services import router as services_router
from . import common, accounts, files, payments, subscriptions, services, bots, bot_reports

# Новые модули
from . import auth, server_map, events

try:
    from . import commands
    HAS_COMMANDS = True
except ImportError:
    HAS_COMMANDS = False

try:
    from . import llm
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

ALL_ROUTERS = [
    auth.router,          # ПЕРВЫМ — перехватывает /start и PIN
    common_router,
    payments_router,
    subscriptions_router,
    accounts_router,
    files_router,
    bots_router,
    bot_reports.router,
    services_router,
    server_map.router,
    events.router,
]

if HAS_COMMANDS:
    ALL_ROUTERS.append(commands.router)

if HAS_LLM:
    ALL_ROUTERS.append(llm.router)

__all__ = ["ALL_ROUTERS", "AuthMiddleware"]