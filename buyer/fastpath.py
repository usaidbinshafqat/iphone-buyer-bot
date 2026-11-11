"""XHR fast path: drive Apple's checkoutx endpoints directly from the parked checkout tab (same cookies, same TLS, same
bot-shield cookies) instead of clicking through the wizard. Field names were captured from our own guest dry run on
2026-10-28 (state/checkoutx_capture.jsonl). Ends by navigating to ?_s=Review so checkout.review_and_place still verifies
product / store / qty / total from the DOM before Place Order. Never reloads the tab (that rewinds the wizard)."""
import json, logging, re, time
from playwright.sync_api import Page
from . import secrets, config
from .checkout import Abort, NeedsHuman, Blocked, shot

log = logging.getLogger("fastpath")

class Unavailable(Exception):
    """Fast path can't start (no token etc.); caller falls back to the UI flow. Raised only before any mutating call."""

JS_POST = r"""
async ([path, query, body, stk, modelPage]) => {
  const res = await fetch(location.origin + path + "?" + query, {
    method: "POST", credentials: "include", signal: AbortSignal.timeout(30000),
    headers: {"Content-Type": "application/x-www-form-urlencoded", "Accept": "*/*",
      "X-Requested-With": "Fetch", "syntax": "graviton", "modelVersion": "v2",
      "x-aos-model-page": modelPage || "checkoutPage", "x-aos-stk": stk,
      "x-aos-ui-fetch-call-1": Math.random().toString(36).slice(2,12) + "-" + Date.now().toString(36)},
    body });
  const text = await res.text(); let j = null; try { j = JSON.parse(text); } catch (e) {}
  return {status: res.status, json: j, raw: text.slice(0, 300)};
}"""

FUL = "checkout.fulfillment."
LOC = FUL + "pickupTab.pickup.storeLocator."
SLOT = FUL + "pickupTab.pickup.timeSlot.dateTimeSlots."
CC = "checkout.billing.billingOptions.selectedBillingOptions.creditCard."

def read_stk(page: Page) -> str | None:
    m = re.search(r'"x-aos-stk"\s*:\s*"([^"]+)"', page.content())
    return m.group(1) if m else None

def _enc(fields) -> str:
    from urllib.parse import urlencode
    return urlencode(fields)

def post(page: Page, stk: str, path: str, a: str, m: str, fields, label: str) -> dict:
    t0 = time.time()
    r = page.evaluate(JS_POST, [path, f"_a={a}&_m={m}", _enc(fields), stk, "checkoutPage"])
    dt = time.time() - t0
    st = r.get("status")
    if st in (541, 503, 429, 403): raise Blocked(f"{st} on {label}")
    j = r.get("json")
    if not j: raise Abort(f"{label}: non-JSON reply (HTTP {st}): {r.get('raw','')[:120]}")
    head = (j.get("head") or {}); hs = head.get("status")
    url = (head.get("data") or {}).get("url", "") if isinstance(head.get("data"), dict) else ""
    if "session_expired" in url or "sorry" in url:
        try: (config.ROOT / "state" / f"fastpath_fail_{label.replace(' ', '_').replace('>', '')}.json").write_text(json.dumps(j)[:400000])
        except Exception: pass
        raise Abort(f"{label}: Apple bounced to {url}; msgs={_messages(j)[:3]}")
    log.info("fastpath %s: HTTP %s head %s in %.1fs", label, st, hs, dt)
    return j

def _messages(j: dict) -> list:
    """Collect ERROR-level messages from any module's `m` arrays."""
    out = []
    def walk(o, depth=0):
        if depth > 8: return
        if isinstance(o, dict):
            m = o.get("m")
            if isinstance(m, list):
                for x in m:
                    if isinstance(x, dict) and x.get("level", "ERROR") == "ERROR" and x.get("text"): out.append(x["text"])
            for v in o.values(): walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o: walk(v, depth + 1)
    walk(j); return out

def _checkout(j: dict) -> dict:
    return ((j.get("body") or {}).get("checkout") or {})

def _find_slots(o, depth=0):
    """Locate the pickup time-slot data: a dict with 'pickUpDates' and 'timeSlotWindows' (tolerant to nesting)."""
    if depth > 12: return None
    if isinstance(o, dict):
        if "timeSlotWindows" in o and "pickUpDates" in o: return o
        for v in o.values():
            r = _find_slots(v, depth + 1)
            if r: return r
    elif isinstance(o, list):
        for v in o:
            r = _find_slots(v, depth + 1)
            if r: return r
    return None

def earliest_slot(j: dict) -> dict | None:
    data = _find_slots(_checkout(j).get("fulfillment") or {}) or _find_slots(j)
    if not data: return None
    dates = data.get("pickUpDates") or []
    wins = data.get("timeSlotWindows") or []
    # timeSlotWindows: list of {dayOfMonth: [slots]} or dict keyed by dayOfMonth, or list of slot dicts
    by_day = {}
    if isinstance(wins, dict): by_day = wins
    else:
        for w in wins:
            if isinstance(w, dict) and not {"SlotId", "signKey"} & set(w):
                for k, v in w.items(): by_day.setdefault(str(k), []).extend(v if isinstance(v, list) else [v])
            elif isinstance(w, dict): by_day.setdefault(str(w.get("dayOfMonth", "")), []).append(w)
    for d in dates:
        day = str(d.get("dayOfMonth", "")); date = d.get("date", "")
        ok = [s for s in by_day.get(day, []) if s.get("enabled", True) and not s.get("isRestricted", False) and s.get("SlotId")]
        if ok:
            # Earliest day, but the LATEST window on it: the earliest window is the one every bot grabs, so a Continue
            # with it is often rejected ("check-in window no longer available"). Config pickup.window: latest|earliest.
            mode = str(config.load().get("pickup", {}).get("window", "3"))
            pick = ok[0] if mode == "earliest" else ok[-1] if mode == "latest" else ok[min(max(int(mode) - 1, 0), len(ok) - 1)]
            return {"date": date, "day": day, "slot": pick, "n_windows": len(ok)}
    return None

def slot_fields(sl: dict) -> list:
    s = sl["slot"]
    return [(SLOT + "startTime", s.get("checkInStart", "")), (SLOT + "displayEndTime", ""), (SLOT + "timeSlotType", ""),
            (SLOT + "isRecommended", "false"), (SLOT + "endTime", s.get("checkInEnd", "")), (SLOT + "date", sl["date"]),
            (SLOT + "timeSlotId", s.get("SlotId", "")), (SLOT + "signKey", s.get("signKey", "")), (SLOT + "timeZone", s.get("timeZone", "")),
            (SLOT + "timeSlotValue", s.get("timeSlotValue", "")), (SLOT + "dayRadio", sl["day"]), (SLOT + "isRestricted", ""), (SLOT + "displayStartTime", "")]

def store_fields(store: str, zip_code: str) -> list:
    return [(LOC + "showAllStores", "false"), (LOC + "selectStore", store), (LOC + "searchInput", zip_code)]

def select_and_continue(page: Page, cfg, store: str, t: int) -> bool:
    """Fulfillment: select store -> earliest window -> continue to PickupContact. Raises Unavailable before mutating."""
    stk = read_stk(page)
    if not stk or "Fulfillment" not in page.url: raise Unavailable("no x-aos-stk / not on fulfillment")
    zip_code = cfg["pickup"]["zip"]
    j = post(page, stk, "/shop/checkoutx/fulfillment", "select", "checkout.fulfillment.pickupTab.pickup.storeLocator", store_fields(store, zip_code), f"select {store}")
    errs = _messages(j)
    if any(re.search(r"unavailable|no availability|not available", e, re.I) for e in errs):
        # the session's store list may be stale (unit appeared after the last search): refresh and retry once
        log.info("select rejected (%s); refreshing store list and retrying once", errs[0][:50])
        post(page, stk, "/shop/checkoutx/fulfillment", "search", "checkout.fulfillment.pickupTab.pickup.storeLocator",
             [(LOC + "showAllStores", "false"), (LOC + "searchInput", zip_code)], "search refresh")
        j = post(page, stk, "/shop/checkoutx/fulfillment", "select", "checkout.fulfillment.pickupTab.pickup.storeLocator", store_fields(store, zip_code), f"select {store} (retry)")
        errs = _messages(j)
        if any(re.search(r"unavailable|no availability|not available", e, re.I) for e in errs):
            raise Abort(f"{store} rejected at select (sold out): {errs[:2]}")
    sl = earliest_slot(j)
    if not sl:
        try: (config.ROOT / "state" / "fastpath_select_debug.json").write_text(json.dumps(j)[:400000])
        except Exception: pass
        log.warning("fastpath: select reply had no pickup windows (msgs=%s); handing store/window step to the UI", errs[:2])
        return False
    log.info("fastpath window %s %s (of %s windows that day)", sl["date"], sl["slot"].get("timeSlotValue") or sl["slot"].get("Label"), sl.get("n_windows"))
    fields = [(FUL + "fulfillmentOptions.selectFulfillmentLocation", "RETAIL")] + store_fields(store, zip_code) + slot_fields(sl)
    j = post(page, stk, "/shop/checkoutx/fulfillment", "continueFromFulfillmentToPickupContact", "checkout.fulfillment", fields, "continue->contact")
    if "pickupContact" not in _checkout(j):
        raise Abort(f"{store} rejected at Continue: {_messages(j)[:2]} keys={list(_checkout(j))}")
    return True

def contact_to_billing(page: Page, cfg, stk: str) -> dict:
    c = cfg.get("contact", {}); P = "checkout.pickupContact."
    fields = [(P + "pickupContactOptions.selectedPickupOption", "SELF"),
              (P + "selfPickupContact.selfContact.address.firstName", c.get("first_name", "")),
              (P + "selfPickupContact.selfContact.address.lastName", c.get("last_name", "")),
              (P + "selfPickupContact.selfContact.address.emailAddress", c.get("email", "")),
              (P + "selfPickupContact.selfContact.address.fullDaytimePhone", c.get("phone", ""))]
    j = post(page, stk, "/shop/checkoutx", "continueFromPickupContactToBilling", "checkout.pickupContact", fields, "contact->billing")
    if "billing" not in _checkout(j): raise Abort(f"contact step rejected: {_messages(j)[:2]} keys={list(_checkout(j))}")
    return j

def billing_to_review(page: Page, cfg, stk: str) -> dict:
    svc = cfg["notify"]["keychain_service"]
    num, exp, cvv = secrets.get(svc, "card_number"), secrets.get(svc, "card_exp"), secrets.get(svc, "card_cvv")
    if not (num and exp and cvv): raise NeedsHuman("Keychain lacks card_number/card_exp/card_cvv")
    b = cfg.get("billing", {}); zip_code = b.get("zip", "")
    gift = [("checkout.billing.billingOptions.selectedBillingOptions.giftCard.giftCardInput.deviceID", '{"op":"DEVICEID"}'),
            ("checkout.billing.billingOptions.selectedBillingOptions.giftCard.giftCardInput.giftCard", "")]
    post(page, stk, "/shop/checkoutx/billing", "selectBillingOptionAction", "checkout.billing.billingOptions",
         [("checkout.billing.billingOptions.selectBillingOption", "CREDIT")] + gift + [("checkout.locationConsent.locationConsent", "false")], "billing option CREDIT")
    jz = post(page, stk, "/shop/checkoutx/billing", "zipLookup", CC + "billingAddress.address.zipLookup",
              [(CC + "billingAddress.address.zipLookup.postalCode", zip_code), (CC + "billingAddress.address.zipLookup.countryCode", "US")], "zip lookup")
    city_state = ""
    txt = json.dumps(jz)
    m = re.search(r'"zipLookupCityState"\s*:\s*\{[^}]*?"d"\s*:\s*"([^"]+)"', txt) or re.search(r'"zipLookupCityState"\s*:\s*"([^"]+)"', txt)
    if m: city_state = m.group(1)
    if not city_state:
        m = re.search(r'"city"\s*:\s*"([^"]+)"[^}]*"state"\s*:\s*"([A-Z]{2})"', txt)
        city_state = f"{m.group(1)}, {m.group(2)}" if m else ""
    log.info("zip lookup -> %r", city_state)
    if not city_state: raise Abort("zip lookup gave no city/state")
    card_type = "VISA" if num.startswith("4") else "MASTERCARD" if num[:1] in "25" else "AMEX" if num[:1] == "3" else "DISCOVER"
    fields = [("checkout.billing.billingOptions.selectBillingOption", "CREDIT"),
              (CC + "billingAddress.address.street2", b.get("street2", "")), (CC + "billingAddress.address.lastName", b.get("last_name", "")),
              (CC + "billingAddress.address.firstName", b.get("first_name", "")), (CC + "billingAddress.address.countryCode", "US"),
              (CC + "billingAddress.address.street", b.get("street", "")), (CC + "billingAddress.address.zipLookup.postalCode", zip_code),
              (CC + "billingAddress.address.zipLookup.zipLookupCityState", city_state), (CC + "billingAddress.address.zipLookup.countryCode", "US"),
              (CC + "cardInputs.cardInput-0.validCardNumber", "true"), (CC + "cardInputs.cardInput-0.cardNumberForBinDetection", ""),
              (CC + "cardInputs.cardInput-0.selectCardType", card_type), (CC + "cardInputs.cardInput-0.securityCode", cvv),
              (CC + "cardInputs.cardInput-0.isSplitPayment", "false"), (CC + "cardInputs.cardInput-0.expiration", exp),
              (CC + "cardInputs.cardInput-0.cardNumber", num)] + gift
    j = post(page, stk, "/shop/checkoutx/billing", "continueFromBillingToReview", "checkout.billing", fields, "billing->review")
    if "review" not in _checkout(j):
        errs = _messages(j)
        if any(re.search(r"card|security code|cvv|declined", e, re.I) for e in errs): raise NeedsHuman(f"Apple rejected the card: {errs[:2]}")
        raise Abort(f"billing step rejected: {errs[:2]} keys={list(_checkout(j))}")
    return j

KEY_RE = re.compile(r'"config"\s*:\s*\{\s*"publicKey"\s*:\s*"([^"]+)"\s*,\s*"publicKeyHash"\s*:\s*"([^"]+)"\s*,\s*"algorithm"\s*:\s*"([^"]+)"')

def read_encryption_key(text: str) -> dict | None:
    """Apple's card-field encryption key (RSA-OAEP, SPKI) as embedded in the Billing page / billing responses."""
    m = KEY_RE.search(text)
    return {"publicKey": m.group(1), "publicKeyHash": m.group(2), "algorithm": m.group(3)} if m else None

JS_ENCRYPT = r"""
async ([spkiB64, alg, value]) => {
  const bin = atob(spkiB64); const buf = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  const key = await crypto.subtle.importKey("spki", buf, {name: alg.toUpperCase() === "RSA-OAEP" ? "RSA-OAEP" : alg, hash: "SHA-256"}, false, ["encrypt"]);
  const ct = await crypto.subtle.encrypt({name: "RSA-OAEP"}, key, new TextEncoder().encode(value.replace(/\s/g, "")));
  return btoa(String.fromCharCode(...new Uint8Array(ct)));
}"""

def encrypt_field(page: Page, key: dict, value: str) -> str:
    ct = page.evaluate(JS_ENCRYPT, [key["publicKey"], key["algorithm"], value])
    return json.dumps({"cipherText": ct, "publicKeyHash": key["publicKeyHash"]}, separators=(",", ":"))

def card(cfg, slot: int = 1) -> tuple | None:
    """(number, exp, cvv) for Keychain slot 1 (card_*) or 2 (card2_*, the backup); None if that slot is incomplete."""
    svc = cfg["notify"]["keychain_service"]; p = "card_" if slot == 1 else f"card{slot}_"
    num, exp, cvv = secrets.get(svc, p + "number"), secrets.get(svc, p + "exp"), secrets.get(svc, p + "cvv")
    return (num, exp, cvv) if (num and exp and cvv) else None

def has_backup_card(cfg) -> bool:
    return card(cfg, 2) is not None

def billing_to_review_encrypted(page: Page, cfg, stk: str, key: dict, slot: int = 1) -> dict:
    """One continueFromBillingToReview carrying CREDIT + encrypted card + billing address (what the UI sends)."""
    c = card(cfg, slot)
    if not c: raise NeedsHuman(f"Keychain lacks card slot {slot} (card_number/card_exp/card_cvv)")
    num, exp, cvv = c
    b = cfg.get("billing", {}); zip_code = b.get("zip", ""); city_state = b.get("city_state", "")
    if not city_state:
        jz = post(page, stk, "/shop/checkoutx/billing", "zipLookup", CC + "billingAddress.address.zipLookup",
                  [(CC + "billingAddress.address.zipLookup.postalCode", zip_code), (CC + "billingAddress.address.zipLookup.countryCode", "US")], "zip lookup")
        m = re.search(r'"zipLookupCityState"\s*:\s*\{[^}]*?"d"\s*:\s*"([^"]+)"', json.dumps(jz)) or re.search(r'"zipLookupCityState"\s*:\s*"([^"]+)"', json.dumps(jz))
        city_state = m.group(1) if m else ""
        if not city_state: raise Abort("zip lookup gave no city/state")
    enc_num, enc_cvv = encrypt_field(page, key, num), encrypt_field(page, key, cvv)
    card_type = "VISA" if num.startswith("4") else "MASTERCARD" if num[:1] in "25" else "AMEX" if num[:1] == "3" else "DISCOVER"
    gift = [("checkout.billing.billingOptions.selectedBillingOptions.giftCard.giftCardInput.deviceID", '{"op":"DEVICEID"}'),
            ("checkout.billing.billingOptions.selectedBillingOptions.giftCard.giftCardInput.giftCard", "")]
    fields = [("checkout.billing.billingOptions.selectBillingOption", "CREDIT"),
              (CC + "billingAddress.address.street2", b.get("street2", "")), (CC + "billingAddress.address.lastName", b.get("last_name", "")),
              (CC + "billingAddress.address.firstName", b.get("first_name", "")), (CC + "billingAddress.address.countryCode", "US"),
              (CC + "billingAddress.address.street", b.get("street", "")), (CC + "billingAddress.address.zipLookup.postalCode", zip_code),
              (CC + "billingAddress.address.zipLookup.zipLookupCityState", city_state), (CC + "billingAddress.address.zipLookup.countryCode", "US"),
              (CC + "cardInputs.cardInput-0.validCardNumber", "true"), (CC + "cardInputs.cardInput-0.cardNumberForBinDetection", ""),
              (CC + "cardInputs.cardInput-0.selectCardType", card_type), (CC + "cardInputs.cardInput-0.securityCode", enc_cvv),
              (CC + "cardInputs.cardInput-0.isSplitPayment", "false"), (CC + "cardInputs.cardInput-0.expiration", exp),
              (CC + "cardInputs.cardInput-0.cardNumber", enc_num)] + gift
    j = post(page, stk, "/shop/checkoutx/billing", "continueFromBillingToReview", "checkout.billing", fields, "billing->review (encrypted)")
    if "review" not in _checkout(j):
        errs = _messages(j)
        if any(re.search(r"unavailable for pickup|no availability|no longer available", e, re.I) for e in errs): raise Abort(f"unit lost at billing (sold out): {errs[0][:80]}")
        if any(re.search(r"card|security code|cvv|declined", e, re.I) for e in errs): raise NeedsHuman(f"Apple rejected the card: {errs[:2]}")
        raise Abort(f"billing step rejected: {errs[:2]} keys={list(_checkout(j))}")
    return j


def run(page: Page, cfg, store: str, t: int) -> str:
    """From a parked Fulfillment page (store list already searched): XHR store select + window + Continue + contact,
    then navigate to the Billing step for the UI (Apple encrypts card fields client-side, so billing stays in the UI).
    Returns "review" (page is on Review), "billing" (page is on Billing, UI does the card) or "fulfillment" (no windows via XHR; caller runs the UI from store select)."""
    t0 = time.time()
    if not select_and_continue(page, cfg, store, t):
        return "fulfillment"
    stk = read_stk(page) or ""
    contact_to_billing(page, cfg, stk)
    origin = re.match(r"https://[^/]+", page.url).group(0)
    page.goto(origin + "/shop/checkout?_s=Billing", wait_until="domcontentloaded", timeout=t * 1000)
    html = page.content()
    if re.search(r"unavailable for pickup at your selected location|no availability within your location", html, re.I):
        raise Abort(f"{store}: unit lost at billing (sold out)")
    key = read_encryption_key(html)
    if not key:
        # the card form (and its key) appears only after the CREDIT option is selected server-side
        gift = [("checkout.billing.billingOptions.selectedBillingOptions.giftCard.giftCardInput.deviceID", '{"op":"DEVICEID"}'),
                ("checkout.billing.billingOptions.selectedBillingOptions.giftCard.giftCardInput.giftCard", "")]
        j = post(page, stk, "/shop/checkoutx/billing", "selectBillingOptionAction", "checkout.billing.billingOptions",
                 [("checkout.billing.billingOptions.selectBillingOption", "CREDIT")] + gift + [("checkout.locationConsent.locationConsent", "false")], "billing option CREDIT")
        key = read_encryption_key(json.dumps(j))
    if not key:
        log.warning("fastpath: no card encryption key found; UI handles billing")
        page.goto(origin + "/shop/checkout?_s=Billing", wait_until="domcontentloaded", timeout=t * 1000)
        log.info("fastpath reached Billing in %.1fs", time.time() - t0)
        return "billing"
    try:
        billing_to_review_encrypted(page, cfg, stk, key)
    except NeedsHuman as e:
        if not ("rejected the card" in str(e) and has_backup_card(cfg)): raise
        log.warning("primary card rejected at billing (%s); retrying with the backup card", str(e)[:120])
        billing_to_review_encrypted(page, cfg, stk, key, slot=2)
    page.goto(origin + "/shop/checkout?_s=Review", wait_until="domcontentloaded", timeout=t * 1000)
    log.info("fastpath reached Review in %.1fs", time.time() - t0)
    return "review"

def rebill(page: Page, cfg, t: int, slot: int) -> None:
    """After a decline at Place Order: go back to Billing, resubmit with the given card slot, return to Review."""
    t0 = time.time()
    origin = re.match(r"https://[^/]+", page.url).group(0)
    page.goto(origin + "/shop/checkout?_s=Billing", wait_until="domcontentloaded", timeout=t * 1000)
    html = page.content()
    if re.search(r"unavailable for pickup at your selected location|no availability within your location", html, re.I):
        raise Abort("unit lost while switching to the backup card (sold out)")
    stk = read_stk(page) or ""
    key = read_encryption_key(html)
    if not key:
        gift = [("checkout.billing.billingOptions.selectedBillingOptions.giftCard.giftCardInput.deviceID", '{"op":"DEVICEID"}'),
                ("checkout.billing.billingOptions.selectedBillingOptions.giftCard.giftCardInput.giftCard", "")]
        j = post(page, stk, "/shop/checkoutx/billing", "selectBillingOptionAction", "checkout.billing.billingOptions",
                 [("checkout.billing.billingOptions.selectBillingOption", "CREDIT")] + gift + [("checkout.locationConsent.locationConsent", "false")], "billing option CREDIT (rebill)")
        key = read_encryption_key(json.dumps(j))
    if not key: raise NeedsHuman("rebill: no card encryption key on the Billing page")
    billing_to_review_encrypted(page, cfg, stk, key, slot=slot)
    page.goto(origin + "/shop/checkout?_s=Review", wait_until="domcontentloaded", timeout=t * 1000)
    log.info("rebill with card slot %s reached Review in %.1fs", slot, time.time() - t0)
