"""Cached daily rates from ExchangeRate-API's free, keyless endpoint."""

from datetime import datetime
from threading import Lock
from time import monotonic

import httpx

API_URL = "https://open.er-api.com/v6/latest/USD"


_CACHE: dict[tuple[str, tuple[str, ...]], tuple[float, dict]] = {}
_CACHE_LOCK = Lock()


def _fetch(base: str, symbols: tuple[str, ...]):
    key = (base, symbols)
    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < 4 * 60 * 60:
            return cached[1].copy()
    response = httpx.get(API_URL, timeout=3.0, follow_redirects=False)
    response.raise_for_status()
    result = response.json()
    usd_rates = result.get("rates")
    valid_response = result.get("result") == "success" and result.get("base_code") == "USD"
    if not valid_response or not isinstance(usd_rates, dict):
        raise ValueError("Unexpected exchange-rate response")
    base_rate = usd_rates.get(base)
    if not isinstance(base_rate, (int, float)) or base_rate <= 0:
        raise ValueError(f"No exchange rate for {base}")
    requested = symbols
    # The provider publishes units per USD. Convert them into source-currency
    # units per one reporting-currency unit for the existing UI calculation.
    rates = {
        code: usd_rates[code] / base_rate
        for code in requested
        if code in usd_rates and isinstance(usd_rates[code], (int, float))
    }
    updated_at = result.get("time_last_update_utc")
    try:
        rate_date = datetime.strptime(updated_at, "%a, %d %b %Y %H:%M:%S %z").date().isoformat()
    except (TypeError, ValueError):
        raise ValueError("Unexpected exchange-rate update timestamp") from None
    value = {
        "base": base,
        "date": rate_date,
        "updated_at": updated_at,
        "rates": rates,
        "provider": "ExchangeRate-API Open Access",
        "provider_url": "https://www.exchangerate-api.com",
    }
    with _CACHE_LOCK:
        _CACHE[key] = (now, value)
    return value.copy()


def latest_rates(base: str, symbols: list[str]):
    base = base.upper()
    symbols = sorted({code.upper() for code in symbols if code.upper() != base})
    invalid_base = not base.isalpha() or len(base) != 3
    invalid_symbols = any(not code.isalpha() or len(code) != 3 for code in symbols)
    if invalid_base or invalid_symbols:
        raise ValueError("Currency codes must be three-letter ISO codes")
    return _fetch(base, tuple(symbols))
