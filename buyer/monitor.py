"""Poll Apple's retail pickup endpoint for one part across nearby stores."""
import logging, httpx

log = logging.getLogger("monitor")
URL = "https://www.apple.com/shop/retail/pickup-message"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.apple.com/shop/buy-iphone/iphone-duo",
    "X-Requested-With": "XMLHttpRequest",
}

class RateLimited(Exception):
    pass

def check_many(parts: list, zip_code: str, wanted_stores: dict, client: httpx.Client | None = None) -> dict:
    """Return {store: {part: {"name", "available", "pickup_display", "quote", "title"}}} for wanted stores."""
    c = client or httpx.Client(timeout=15)
    params = {"pl": "true", "location": zip_code}
    for i, p in enumerate(parts): params[f"parts.{i}"] = p
    r = c.get(URL, params=params, headers=HEADERS)
    if r.status_code in (541, 503, 429, 403):
        raise RateLimited(f"HTTP {r.status_code}")
    r.raise_for_status()
    body = r.json()["body"]
    if body.get("errorMessage"):
        raise RuntimeError(f"apple error: {body['errorMessage']}")
    out = {}
    for s in body.get("stores", []):
        num = s.get("storeNumber")
        if num not in wanted_stores:
            continue
        out[num] = {}
        for part in parts:
            pa = s["partsAvailability"].get(part, {})
            reg = pa.get("messageTypes", {}).get("regular", {})
            out[num][part] = {"name": s.get("storeName"), "available": pa.get("pickupDisplay") == "available",
                              "pickup_display": pa.get("pickupDisplay"), "quote": pa.get("pickupSearchQuote"),
                              "title": reg.get("storePickupProductTitle")}
    return out

def check(part: str, zip_code: str, wanted_stores: dict, client: httpx.Client | None = None) -> dict:
    """Return {store_number: {"name":..., "available": bool, "quote": str, "title": str}} for wanted stores."""
    c = client or httpx.Client(timeout=15)
    r = c.get(URL, params={"pl": "true", "parts.0": part, "location": zip_code}, headers=HEADERS)
    if r.status_code in (541, 503, 429, 403):
        raise RateLimited(f"HTTP {r.status_code}")
    r.raise_for_status()
    body = r.json()["body"]
    if body.get("errorMessage"):
        raise RuntimeError(f"apple error: {body['errorMessage']}")
    out = {}
    for s in body.get("stores", []):
        num = s.get("storeNumber")
        if num not in wanted_stores:
            continue
        pa = s["partsAvailability"].get(part, {})
        reg = pa.get("messageTypes", {}).get("regular", {})
        out[num] = {
            "name": s.get("storeName"),
            "available": pa.get("pickupDisplay") == "available",
            "pickup_display": pa.get("pickupDisplay"),
            "quote": pa.get("pickupSearchQuote"),
            "title": reg.get("storePickupProductTitle"),
        }
    missing = set(wanted_stores) - set(out)
    if missing:
        log.warning("stores missing from response: %s", missing)
    return out
