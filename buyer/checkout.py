"""Playwright checkout driver. Every step dumps a screenshot so failures are diagnosable.

Flow: bag -> checkout -> fulfillment (pickup, store) -> pickup details -> payment (saved card + CVV)
      -> review -> Place Order (only when dry_run is false).
"""
import logging, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
from . import config, secrets

log = logging.getLogger("checkout")
SHOTS = config.ROOT / "state" / "shots"
DEFAULT_CLICKS = ["dimensionColornightsky", "dimensionCapacity512gb", "choose-noTradeIn",
                  "purchaseGroupOptionfullprice", "carrierModelUNLOCKED/US", "noapplecare"]

class Abort(Exception):
    """Unrecoverable for this attempt; monitor may retry later."""

class Blocked(Exception):
    """Apple answered a checkout call with 541/503/429 (bot shield / IP budget)."""

class NeedsHuman(Exception):
    """Sign-in / 2FA / CAPTCHA / bank verification: notify and stop."""

def shot(page: Page, name: str) -> str:
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{time.strftime('%Y%m%d-%H%M%S')}_{name}.png"
    try: page.screenshot(path=str(p), full_page=name in ("review", "after_place", "attempt_abort"))
    except Exception as e: log.warning("screenshot failed: %s", e)
    return str(p)

def body(page: Page) -> str:
    try: return page.locator("body").inner_text(timeout=5000)
    except Exception: return ""

def money(s: str) -> float | None:
    m = re.search(r"\$\s?([\d,]+\.\d{2})", s)
    return float(m.group(1).replace(",", "")) if m else None

def type_into(el, value: str, label: str = "field"):
    """Apple's React inputs ignore instant fill; type keystrokes and verify."""
    value = str(value)
    for attempt in range(3):
        el.scroll_into_view_if_needed(); el.focus(); time.sleep(0.05)
        if el.input_value():
            el.press("Meta+A"); el.press("Backspace")
        el.press_sequentially(value, delay=25); time.sleep(0.15)
        got = re.sub(r"\D", "", el.input_value()) if re.fullmatch(r"[\d/ ]+", value) else el.input_value().strip()
        want = re.sub(r"\D", "", value) if re.fullmatch(r"[\d/ ]+", value) else value
        if got == want:
            return
        log.warning("%s typed value mismatch (attempt %s): got %r", label, attempt + 1, got[:4] + "…")
    raise Abort(f"could not enter {label}")

def click_continue(page: Page, t: int):
    """Click the step's primary continue button (Apple names them *-continue-button)."""
    loc = page.locator('button[data-autom$="continue-button"]:visible, button[data-autom*="continue"]:visible')
    if not loc.count():
        loc = page.get_by_role("button", name=re.compile(r"continue", re.I))
    loc.first.click(timeout=t * 1000)

def ensure_bag(page: Page, cfg, t: int, variant: dict, qty: int = 1):
    """Make the bag hold exactly `qty` of `variant` and nothing else."""
    exp = variant["expected_title"]
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded")
    deadline = time.time() + t
    while True:   # bag renders -> go on; Apple's "Page Not Found" (outage / 541) -> fail fast so the caller retries soon
        if page.locator('[data-autom="checkout"], [data-autom="bag-item-name"], :text("Your Bag is empty")').count(): break
        if "Page Not Found" in (page.title() or "") or "/shop/404" in page.url:
            raise Blocked("bag answered with Apple's Page Not Found (outage or 541)")
        if time.time() > deadline: raise PWTimeout(f"bag did not render within {t}s")
        time.sleep(0.25)
    names = [n.replace("\xa0", " ") for n in page.locator('[data-autom="bag-item-name"]').all_inner_texts()]
    if names and not (len(names) == 1 and exp.lower() in names[0].lower()):
        log.info("bag has %s; clearing", names)
        while page.locator('[data-autom="bag-item-remove-button"]').count():
            page.locator('[data-autom="bag-item-remove-button"]').first.click(); time.sleep(2.5)
        names = []
    if not names:
        log.info("adding %s to bag", exp)
        add_to_bag(page, cfg, t, variant)
        page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded")
        deadline = time.time() + t
        while True:   # bag item appears -> fine; Apple's "Page Not Found" (outage / 541) -> fail fast so the caller retries soon
            if page.locator('[data-autom="bag-item-name"]').count(): break
            if "Page Not Found" in (page.title() or "") or "/shop/404" in page.url:
                raise Blocked("bag answered with Apple's Page Not Found (outage or 541)")
            if time.time() > deadline: raise PWTimeout(f"bag items did not render within {t}s")
            time.sleep(0.25)
        names = [n.replace("\xa0", " ") for n in page.locator('[data-autom="bag-item-name"]').all_inner_texts()]
    if len(names) != 1 or exp.lower() not in names[0].lower():
        shot(page, "bag_bad"); raise Abort(f"bag must contain exactly one line of '{exp}', found {names}")
    q = page.locator('[data-autom="item-quantity-dropdown"]').first
    if q.count() and q.input_value() != str(qty):
        opts = [o.get_attribute("value") for o in q.locator("option").all()]
        if str(qty) not in opts:
            raise Abort(f"quantity {qty} not offered (options {opts})")
        q.select_option(str(qty)); time.sleep(3)
        page.wait_for_selector('[data-autom="checkout"]', timeout=t * 1000)
        if page.locator('[data-autom="item-quantity-dropdown"]').first.input_value() != str(qty):
            raise Abort(f"could not set quantity {qty}")
    log.info("bag OK: %s x%s", names[0], qty)

def add_to_bag(page: Page, cfg, t: int, variant: dict):
    page.goto(variant["product_url"], wait_until="domcontentloaded")
    page.wait_for_selector('[data-autom="add-to-cart"]', timeout=t * 1000)
    for a in variant.get("configurator_clicks", DEFAULT_CLICKS):
        el = page.locator(f'[data-autom="{a}"]').first
        el.scroll_into_view_if_needed(); el.click(force=True); time.sleep(0.6)
    price = money(page.locator('[data-autom="purchaseGroupOptionfullprice"]').locator("xpath=ancestor::fieldset").inner_text())
    if price and price > cfg["product"]["max_unit_price_usd"]:
        raise Abort(f"configurator price {price} exceeds cap")
    page.locator('[data-autom="add-to-cart"]').click()
    page.wait_for_url(re.compile(r"step=attach|/shop/bag"), timeout=t * 1000)

def _try_sign_in(page: Page, t: int, svc: str) -> bool:
    """Apple's checkout sign-in (idmsa iframe). Returns True if we reached checkout signed in."""
    user, pw = secrets.get(svc, "apple_id"), secrets.get(svc, "apple_id_password")
    if not (user and pw): return False
    fr = next((f for f in page.frames if "idmsa.apple.com" in f.url), None)
    if fr is None: return False
    try:
        acct = fr.locator("#account_name_text_field"); acct.wait_for(timeout=8000)
        chooser = fr.locator('button:has-text("Continue with Password")')
        pwd = fr.locator("#password_text_field")
        if not acct.input_value().strip():
            acct.focus(); acct.press_sequentially(user, delay=15)
        # With a remembered email Apple may show the chooser ("Continue with Password" / Passkey)
        # straight away; otherwise Continue (#sign-in) leads to it or directly to the password field.
        if not (chooser.count() and chooser.first.is_visible()) and not (pwd.count() and pwd.first.is_visible()):
            fr.locator("#sign-in").click()
        deadline = time.time() + 10
        while time.time() < deadline:
            if chooser.count() and chooser.first.is_visible(): chooser.first.click(); break
            if pwd.count() and pwd.first.is_visible() and pwd.first.input_value() == "" and not chooser.count(): break
            time.sleep(0.2)
        pwd.first.wait_for(timeout=8000); time.sleep(0.3)
        pwd.first.focus(); pwd.first.press_sequentially(pw, delay=15)
        fr.locator("#sign-in").click()
    except Exception as e:
        log.warning("sign-in form interaction failed: %s", str(e)[:120]); return False
    deadline = time.time() + t
    while time.time() < deadline:
        if "checkout" in page.url and page.get_by_text(re.compile("pick it up")).count():
            log.info("signed in at checkout"); return True
        fr = next((f for f in page.frames if "idmsa.apple.com" in f.url), None)
        if fr is not None:
            try:
                txt = fr.locator("body").inner_text(timeout=2000)
                if re.search(r"verification code|two-factor|Two-Factor|trust this browser|incorrect|locked", txt, re.I):
                    shot(page, "signin_challenge"); log.warning("sign-in challenge: %s", txt[:120].replace("\n", " ")); return False
            except Exception: pass
        time.sleep(0.4)
    log.warning("sign-in did not reach checkout in %ss", t); return False

def go_checkout(page: Page, t: int, cfg=None):
    page.locator('[data-autom="checkout"]').first.click()
    page.wait_for_url(re.compile(r"secure\d*\.store\.apple\.com"), timeout=t * 1000)
    # signed-in sessions skip the sign-in page; otherwise try Apple ID sign-in (Keychain), else continue as guest.
    deadline = time.time() + 2 * t; clicked_guest = 0; tried_signin = False
    svc = (cfg or {}).get("notify", {}).get("keychain_service", "apple-buyer")
    while time.time() < deadline:
        if "checkout" in page.url and page.get_by_text(re.compile("pick it up")).count():
            return
        g = page.locator('[data-autom="guest-checkout-btn"]')
        if g.count() and not tried_signin and (cfg or {}).get("checkout", {}).get("sign_in", True):
            tried_signin = True
            if _try_sign_in(page, t, svc): return
            log.warning("falling back to guest checkout")
        if g.count() and time.time() - clicked_guest > 10:
            shot(page, "signin_page"); log.warning("not signed in; continuing as guest")
            try: g.first.click(timeout=5000)
            except Exception as e: log.info("guest click: %s", str(e)[:80])
            clicked_guest = time.time()
        time.sleep(0.5)
    shot(page, "checkout_stuck"); raise Abort(f"checkout page never loaded: {page.url}")

def select_pickup(page: Page, cfg, store: str, t: int):
    """Fulfillment page: pickup tab -> zip search -> store radio -> earliest date -> earliest window -> continue."""
    tab = page.get_by_text(re.compile("pick it up")).first
    tab.wait_for(timeout=t * 1000); tab.click(); time.sleep(0.3)
    radio = page.locator(f'input[type="radio"][value="{store}"]')
    err_box = page.locator(':text("unavailable for pickup at your selected location"), :text("no availability within your location")')
    zip_code = cfg["pickup"]["zip"]
    def search_zip():
        inp = page.locator('[data-autom="bag-storelocator-input"]')
        if not (inp.count() and inp.first.is_visible()):
            b = page.locator('[data-autom="fulfillment-pickup-store-search-button"]')
            b.first.wait_for(timeout=t * 1000); b.first.click(); time.sleep(1)
            inp = page.locator('[data-autom="bag-storelocator-input"]')
        inp.first.fill(zip_code); inp.first.press("Enter")
    try:
        radio.first.wait_for(timeout=4000)
    except PWTimeout:
        search_zip(); radio.first.wait_for(timeout=t * 1000)
    time.sleep(0.4)
    label = radio.first.locator("xpath=ancestor::*[self::label or self::div][1]").inner_text()
    if re.search(r"unavailable", label, re.I):
        shot(page, "store_unavailable"); raise Abort(f"{store} shows unavailable in checkout: {label!r}")
    radio.first.check(force=True)
    dd = page.locator('[data-autom="pickup-availablewindow-dropdown"]').first
    # fast race: either the window dropdown appears or Apple rejects the store; don't sit on a long timeout
    deadline = time.time() + t
    while True:
        if dd.count() and dd.is_visible(): break
        if err_box.count() and err_box.first.is_visible():
            shot(page, "store_rejected"); raise Abort(f"{store} rejected after select (sold out)")
        if time.time() > deadline:
            shot(page, "no_dropdown"); raise Abort(f"{store}: no pickup windows appeared within {t}s")
        time.sleep(0.15)
    time.sleep(0.5)
    # earliest enabled pickup date (Apple pre-selects one; we take the first enabled)
    dates = page.locator('fieldset:has-text("pickup date") input[type="radio"]')
    for i in range(dates.count()):
        d = dates.nth(i)
        if d.is_enabled():
            if not d.is_checked():
                d.check(force=True); time.sleep(0.6)
                dd = page.locator('[data-autom="pickup-availablewindow-dropdown"]').first; dd.wait_for(timeout=t * 1000)
            break
    # earliest window: option 0 is the "Available Windows" placeholder
    opts = dd.locator("option")
    vals = [opts.nth(i).get_attribute("value") for i in range(opts.count())]
    real = [v for v in vals if v]
    if not real: shot(page, "no_windows"); raise Abort("no pickup windows offered")
    dd.select_option(real[0]); time.sleep(0.3)
    log.info("pickup %s, window %s", store, real[0])
    page.locator('[data-autom="fulfillment-continue-button"]').click()
    deadline = time.time() + t
    while not re.search(r"PickupContact|Billing|Payment", page.url, re.I):
        if err_box.count() and err_box.first.is_visible():
            shot(page, "continue_rejected"); raise Abort(f"{store} rejected at Continue (sold out)")
        if time.time() > deadline:
            shot(page, "continue_timeout"); raise Abort(f"{store}: Continue did not advance within {t}s (url={page.url})")
        time.sleep(0.15)
    time.sleep(0.4)

def pickup_contact(page: Page, cfg, t: int):
    """Who picks up: self, with name/email/phone (prefilled when signed in; filled from config otherwise)."""
    if "PickupContact" not in page.url:
        return
    shot(page, "pickup_contact")
    sp = page.locator('[data-autom="selfPickup"]')
    if sp.count(): sp.first.click(); time.sleep(0.2)
    contact = cfg.get("contact", {})
    for field, key in [("firstName", "first_name"), ("lastName", "last_name"), ("emailAddress", "email"), ("fullDaytimePhone", "phone")]:
        el = page.locator(f'[data-autom="form-field-{field}"]')
        if el.count() and el.first.is_visible() and not el.first.input_value().strip():
            val = contact.get(key)
            if not val:
                raise NeedsHuman(f"pickup contact field {field} is empty and config.contact.{key} not set")
            type_into(el.first, str(val), f"contact {field}")
    page.locator('[data-autom="continue-button-label"]').first.click()
    page.wait_for_url(re.compile(r"Billing|Payment", re.I), timeout=t * 1000); time.sleep(0.3)

def payment(page: Page, cfg, t: int):
    """Billing page. Saved card (signed in) -> CVV only. Otherwise full card + billing address from Keychain/config."""
    page.wait_for_url(re.compile(r"Billing|Payment", re.I), timeout=t * 1000); time.sleep(0.4)
    txt = body(page)
    if re.search(r"captcha|verify (it's|its) you|verification code", txt, re.I):
        raise NeedsHuman("Apple is asking for verification on the payment page")
    svc = cfg["notify"]["keychain_service"]
    credit = page.locator('[data-autom="checkout-billingOptions-CREDIT"]')
    card_in = page.locator('[data-autom="card-number-input"]')
    cvv_any = page.locator('[data-autom="security-code-input"]')
    if credit.count():
        try: credit.first.click(force=True)
        except Exception: credit.first.check(force=True)
        for attempt in range(2):
            try:
                page.locator('[data-autom="card-number-input"], [data-autom="security-code-input"]').first.wait_for(timeout=2500 if attempt == 0 else 8000); break
            except PWTimeout:
                if attempt == 0:  # Apple sometimes reveals the card form only after a first Continue click
                    log.info("card form not shown yet; nudging with Continue")
                    try:
                        with page.expect_response(lambda r: "continueFromBillingToReview" in r.url, timeout=10000):
                            page.locator('[data-autom="continue-button-review"]').first.click()
                    except PWTimeout:
                        pass
                    time.sleep(1)  # let the re-render settle before typing
    guest_form = bool(card_in.count() and card_in.first.is_visible())
    def fill_guest_form():
        num, exp, cvv = secrets.get(svc, "card_number"), secrets.get(svc, "card_exp"), secrets.get(svc, "card_cvv")
        if not (num and exp and cvv):
            raise NeedsHuman("Apple shows a blank card form and Keychain lacks card_number/card_exp/card_cvv (run scripts/setup_secrets.py)")
        b = cfg.get("billing", {}); c = cfg.get("contact", {})
        plan = [("card-number-input", num, "card number"), ("expiration-input", exp, "expiry"), ("security-code-input", cvv, "cvv"),
                ("form-field-firstName", b.get("first_name") or c.get("first_name"), "billing first name"),
                ("form-field-lastName", b.get("last_name") or c.get("last_name"), "billing last name"),
                ("form-field-street", b.get("street"), "billing street"), ("form-field-street2", b.get("street2", ""), "billing street2"),
                ("form-field-postalCode", b.get("zip"), "billing zip")]
        for autom, val, label in plan:
            el = page.locator(f'[data-autom="{autom}"]')
            if not (el.count() and el.first.is_visible()): continue
            if el.first.input_value().strip(): continue  # already holds a (possibly masked) value
            if not val:
                if autom == "form-field-street2": continue
                raise NeedsHuman(f"{label} missing in config.yaml")
            type_into(el.first, str(val), label); time.sleep(0.05)
        cs = page.locator('[data-autom="form-field-zipLookupCityState"]')  # async zip lookup
        for _ in range(50):
            if cs.count() and cs.first.input_value().strip(): break
            time.sleep(0.2)
    if guest_form:
        fill_guest_form(); log.info("entered card + billing address")
    else:
        cvv_in = page.locator('[data-autom="security-code-input"]:visible, input[autocomplete="cc-csc"]:visible, input[name*="securityCode" i]:visible, input[name*="cvv" i]:visible')
        if cvv_in.count():
            code = secrets.get(svc, "card_cvv")
            if not code: raise NeedsHuman("no card_cvv in Keychain; run scripts/setup_secrets.py")
            type_into(cvv_in.first, code, "cvv"); log.info("CVV entered for saved card")
        else:
            log.info("no card or CVV field visible; assuming saved card needs nothing")
    review = page.locator(':text("Payment Details"), button:has-text("Place Order")')
    for attempt in range(3):
        if not guest_form and card_in.count() and card_in.first.is_visible():
            guest_form = True; log.info("card form appeared late; filling it")
        if guest_form:
            fill_guest_form()  # re-type anything a re-render wiped
            empties = [a for a in ("card-number-input", "expiration-input", "security-code-input", "form-field-firstName", "form-field-street", "form-field-postalCode")
                       if page.locator(f'[data-autom="{a}"]').count() and not page.locator(f'[data-autom="{a}"]').first.input_value().strip()]
            if empties: log.warning("fields still empty before continue: %s", empties)
        page.locator('[data-autom="continue-button-review"]').first.click()
        try:
            review.first.wait_for(timeout=12000); break
        except PWTimeout:
            errs = [e.strip() for e in page.locator('[role="alert"], .form-message, .is-error').all_inner_texts() if e.strip()][:6]
            log.warning("billing continue attempt %s did not reach review; messages=%s", attempt + 1, errs)
            if any(re.search(r"unavailable for pickup|no availability|no longer available", e, re.I) for e in errs):
                shot(page, "lost_at_billing"); raise Abort(f"unit lost at billing (sold out): {errs[0][:80]}")
            if attempt == 2:
                shot(page, "payment_stuck"); raise Abort(f"payment page did not advance; messages: {errs}")
    time.sleep(0.5)
    txt = body(page)
    if re.search(r"(card|security code|cvv).{0,40}(invalid|incorrect|declined|not valid)", txt, re.I):
        shot(page, "card_rejected"); raise NeedsHuman("Apple rejected the card details")

def review_and_place(page: Page, cfg, store: str, variant: dict, qty: int, notifier, lock, t: int, card_slot: int = 1) -> dict:
    time.sleep(0.5); s = shot(page, "review")
    txt = body(page)
    exp = variant["expected_title"]; store_name = cfg["pickup"]["stores"][store]
    if exp.lower() not in txt.lower():
        raise Abort("review page does not show the expected product")
    if store_name.lower() not in txt.lower():
        raise Abort(f"review page does not mention {store_name}")
    m = re.search(r"Quantity for [^\n]*\n\s*(\d+)", txt)
    shown_qty = int(m.group(1)) if m else None
    if shown_qty != qty:
        raise Abort(f"review quantity {shown_qty} != planned {qty}")
    # Apple prints "Total" and the amount on separate lines; take the amount following the last standalone "Total"
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    total = None
    for i, l in enumerate(lines):
        if re.fullmatch(r"total", l, re.I) and i + 1 < len(lines):
            total = money(lines[i + 1]) or total
    log.info("review totals section: %s", [l for l in lines if re.search(r"total|\$", l, re.I)][-8:])
    cap = min(cfg["product"]["max_order_total_usd"], qty * cfg["product"]["max_unit_price_usd"])
    if not total or total > cap:
        raise Abort(f"order total {total} missing or exceeds cap {cap}")
    place = page.locator('[data-autom="continue-button-placeOrder"]')
    if not place.count():
        place = page.get_by_role("button", name=re.compile(r"place (your )?order", re.I))
    if not place.count():
        raise Abort("no Place Order button on review page")
    if cfg["checkout"]["dry_run"]:
        notifier.send(f"DRY RUN: ready to place order. {exp} x{qty} at {store_name}, total ${total:.2f}. NOT submitting.", s)
        return {"dry_run": True, "total": total}
    oid = lock.start_order(variant["part_number"], qty, store, total)
    place.first.click()
    # Poll up to 60s for: a confirmation page, OR Apple bouncing us back to the store list (unit taken at the last check).
    deadline = time.time() + 60; bounced = False
    while time.time() < deadline:
        if re.search(r"thankyou|orderConfirm|confirmation", page.url, re.I): break
        if "_s=Fulfillment" in page.url or page.locator(':text("unavailable for pickup at your selected location"), :text("no availability within your location")').count():
            bounced = True; break
        if page.locator(':text("Thank you for your order"), :text("order has been placed")').count(): break
        time.sleep(0.5)
    time.sleep(1.5); s2 = shot(page, "after_place")
    txt = body(page)
    if bounced or re.search(r"unavailable for pickup at your selected location|no availability within your location", txt, re.I):
        lock.finish_order(oid, "failed", None, "Place Order bounced: unit unavailable at the final check")
        raise Abort(f"{store_name}: unit lost at Place Order (sold out at the final check)")
    if re.search(r"payment authorization failed|card was declined|declined", txt, re.I):
        lock.finish_order(oid, "failed", None, f"Place Order: payment authorization failed (card slot {card_slot} declined)")
        from . import fastpath
        if card_slot == 1 and fastpath.has_backup_card(cfg):
            # Primary declined while we still hold the unit: swap to the backup card and place again (one retry).
            log.warning("CARD DECLINED (primary) at Place Order; retrying with the backup card")
            notifier.send(f"🚨 Primary card declined at Place Order for {exp} at {store_name}; retrying with the backup card now.", s2)
            fastpath.rebill(page, cfg, t, slot=2)
            return review_and_place(page, cfg, store, variant, qty, notifier, lock, t, card_slot=2)
        notifier.send(f"🚨 CARD DECLINED at Place Order for {exp} at {store_name} (card slot {card_slot}). We had the unit. Send a working card now.", s2)
        raise NeedsHuman("card declined at Place Order")
    m = re.search(r"(W\d{9,}|Order (?:Number|#)[:\s]*([A-Z0-9]{6,}))", txt)
    order = (m.group(2) or m.group(1)) if m else None
    if order or re.search(r"thank you for your order|order (has been )?placed", txt, re.I):
        lock.finish_order(oid, "confirmed", order)
        notifier.send(f"✅ ORDER PLACED by the bot: {exp} x{qty} at {store_name}, total ${total:.2f}, order {order or '(see screenshot)'}. "
                      f"Devices so far: {lock.total_units()}/{cfg['product']['want_total']}", s2)
        return {"order": order, "total": total}
    lock.finish_order(oid, "submitted", None, "click sent, no confirmation detected")
    notifier.send("Place Order clicked but no confirmation detected. Bot paused. Check apple.com/orders, then edit state/purchase.lock.json "
                  "(set that order's phase to 'confirmed' or 'failed') to resume.", s2)
    raise NeedsHuman("unconfirmed order")

def buy(page: Page, cfg, store: str, variant: dict, qty: int, notifier, lock, t: int, staged: bool = False) -> dict:
    """Full flow on an already-open page. Falls back from qty 2 to 1 if the store can't fulfil 2.
    staged=True: caller guarantees the bag already holds exactly this variant x qty and the page is on fulfillment."""
    if not staged:
        ensure_bag(page, cfg, t, variant, qty)
        go_checkout(page, t, cfg)
    if staged and qty == 1 and cfg["checkout"].get("fastpath", False):
        from . import fastpath
        try:
            stage = fastpath.run(page, cfg, store, t)
            if stage == "review":
                return review_and_place(page, cfg, store, variant, qty, notifier, lock, t)
            if stage == "billing":
                payment(page, cfg, t)
                return review_and_place(page, cfg, store, variant, qty, notifier, lock, t)
        except fastpath.Unavailable as e:
            log.warning("fast path unavailable (%s); using UI flow", e)
    try:
        select_pickup(page, cfg, store, t)
    except Abort as e:
        if qty > 1:
            log.warning("qty %d not available at %s (%s); retrying with 1", qty, store, e)
            return buy(page, cfg, store, variant, 1, notifier, lock, t)
        raise
    pickup_contact(page, cfg, t)
    payment(page, cfg, t)
    return review_and_place(page, cfg, store, variant, qty, notifier, lock, t)

def run_checkout(cfg, store: str, notifier, lock, part: str | None = None, qty: int = 1) -> int:
    t = cfg["checkout"]["timeout_seconds"]
    from .plan import variant as _variant
    variant = _variant(cfg, part or cfg["product"]["variants"][0]["part_number"])
    if lock.has_unconfirmed():
        log.error("unconfirmed order in ledger; refusing to checkout"); return 2
    if store not in cfg["pickup"]["stores"]:
        log.error("store %s not allowed", store); return 2
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(cfg["checkout"]["chrome_profile_dir"], channel="chrome", headless=False,
            viewport={"width": 1280, "height": 1000}, ignore_default_args=["--enable-automation"], args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(t * 1000)
        try:
            buy(page, cfg, store, variant, qty, notifier, lock, t); return 0
        except NeedsHuman as e:
            notifier.send(f"NEEDS YOU: {e}", shot(page, "needs_human")); log.error("needs human: %s", e); return 3
        except Abort as e:
            notifier.send(f"checkout aborted at {store}: {e}", shot(page, "abort")); log.error("abort: %s", e); return 1
        except Exception as e:
            notifier.send(f"checkout crashed at {store}: {type(e).__name__}: {str(e)[:200]}", shot(page, "crash")); log.exception("crash"); return 1
        finally:
            ctx.close()
