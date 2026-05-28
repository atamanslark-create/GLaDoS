"""
GLaDoS — утилиты.

Генератор паролей, проверка транзакций TRON (TRC20 USDT),
курсы валют через CoinGecko.
"""

import secrets
import string

import aiohttp

# ── Генератор паролей ───────────────────────────────────────────────────────

def generate_password(length: int = 20, use_special: bool = True) -> str:
    alphabet = string.ascii_letters + string.digits
    if use_special:
        alphabet += "!@#$%^&*_+-="
    # Гарантируем хотя бы по одному символу каждого типа
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        has_upper = any(c in string.ascii_uppercase for c in pwd)
        has_lower = any(c in string.ascii_lowercase for c in pwd)
        has_digit = any(c in string.digits for c in pwd)
        has_spec = (not use_special) or any(c in "!@#$%^&*_+-=" for c in pwd)
        if has_upper and has_lower and has_digit and has_spec:
            return pwd


# ── Проверка транзакций TRON ────────────────────────────────────────────────

TRONGRID_URL = "https://api.trongrid.io"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # USDT TRC20 mainnet


async def check_tron_tx(tx_hash: str) -> dict | None:
    """
    Проверяет транзакцию по хешу через TronGrid API.
    Возвращает словарь с данными или None при ошибке.
    """
    url = f"{TRONGRID_URL}/v1/transactions/{tx_hash}/events"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                data = await resp.json()

        if not data.get("data"):
            # Попробуем основной эндпоинт для инфы о транзакции
            return await _check_tx_info(tx_hash)

        events = data["data"]
        result = {
            "hash": tx_hash,
            "confirmed": True,
            "events": [],
        }
        for ev in events:
            if ev.get("contract_address") == USDT_CONTRACT:
                # Суммы в USDT приходят в sun (6 decimals)
                raw_amount = int(ev.get("result", {}).get("value", 0))
                result["events"].append({
                    "type": "USDT TRC20",
                    "from": ev.get("result", {}).get("from", "?"),
                    "to": ev.get("result", {}).get("to", "?"),
                    "amount": raw_amount / 1_000_000,
                })
            else:
                result["events"].append({
                    "type": ev.get("event_name", "unknown"),
                    "contract": ev.get("contract_address", "?"),
                })
        return result
    except Exception as e:
        return {"error": str(e)}


async def _check_tx_info(tx_hash: str) -> dict | None:
    url = f"{TRONGRID_URL}/wallet/gettransactionbyid"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"value": tx_hash},
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                data = await resp.json()
        if not data or "txID" not in data:
            return {"error": "Транзакция не найдена в сети TRON."}
        ret = data.get("ret", [{}])
        status = ret[0].get("contractRet", "UNKNOWN") if ret else "UNKNOWN"
        return {
            "hash": tx_hash,
            "confirmed": status == "SUCCESS",
            "status": status,
            "events": [],
        }
    except Exception as e:
        return {"error": str(e)}


# ── Курсы валют (CoinGecko) ────────────────────────────────────────────────

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


async def get_usdt_rates() -> dict | None:
    """
    Возвращает курсы USDT к USD, RUB, EUR, BTC или None при ошибке.
    """
    params = {
        "ids": "tether",
        "vs_currencies": "usd,rub,eur,btc",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_URL, params=params,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        return data.get("tether")
    except Exception:
        return None
