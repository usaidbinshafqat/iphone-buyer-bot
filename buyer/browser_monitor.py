"""Browser monitor: parks Chrome on the checkout fulfillment step (preferred variant x1 in bag) and re-runs the zip store
search. Cadence is two-speed: a slow keep-warm search when no watcher sees stock (Apple budgets checkoutx per exit IP;
~70 calls trips HTTP 541), and a back-to-back burst for hot_seconds whenever a watcher drops state/trigger.json.
A 541 / shop/404 means we are blocked: go silent for a cooldown (escalating), then relaunch on a fresh Chrome profile.
The checkout session is rebuilt before Apple's 20-minute TTL. Buys per buyer.plan until want_total devices are confirmed."""
import json, logging, random, re, shutil, time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
from . import checkout as co, plan

log = logging.getLogger("browser_monitor")
TRIGGER = Path(co.config.ROOT) / "state" / "trigger.json"

Blocked = co.Blocked

class DeliveryOnly(Exception):
    """Apple flipped the parked checkout to 'only eligible for delivery' (no store list at all): rebuild at once."""

def _delivery_only(page: Page) -> bool:
    try: return page.locator(':text("only eligible for delivery")').count() > 0
    except Exception: return False

def _store_states(page: Page, wanted: dict) -> dict:
    out = {}
    for store in wanted:
        r = page.locator(f'input[type="radio"][value="{store}"]')
        if not r.count(): continue
        label = r.first.locator("xpath=ancestor::*[self::label or self::div][1]").inner_text()
        out[store] = {"available": not re.search(r"unavailable", label, re.I), "label": re.sub(r"\s+", " ", label)[:80]}
    return out

def _check_blocked(page: Page):
    if "/shop/404" in page.url: raise Blocked(f"landed on {page.url}")

def _to_fulfillment(page: Page, cfg, t: int, variant: dict):
    co.ensure_bag(page, cfg, t, variant, 1); _check_blocked(page)
    co.go_checkout(page, t, cfg); _check_blocked(page)
    tab = page.get_by_text(re.compile("pick it up")).first
    tab.wait_for(timeout=t * 1000)
    with page.expect_response(lambda r: "checkoutx/fulfillment" in r.url, timeout=t * 1000) as ri:
        tab.click()
    if ri.value.status == 541: raise Blocked("541 on pickup tab")
    time.sleep(1); _check_blocked(page)

def _search(page: Page, cfg, t: int):
    if _delivery_only(page): raise DeliveryOnly("before search")
    inp = page.locator('[data-autom="bag-storelocator-input"]')
    if not (inp.count() and inp.first.is_visible()):
        _check_blocked(page)
        b = page.locator('[data-autom="fulfillment-pickup-store-search-button"]')
        b.first.wait_for(timeout=t * 1000); b.first.click(); time.sleep(0.8)
        inp = page.locator('[data-autom="bag-storelocator-input"]')
    inp.first.fill(cfg["pickup"]["zip"])
    t0 = time.time()
    with page.expect_response(lambda r: "checkoutx/fulfillment" in r.url and "_a=search" in r.url, timeout=t * 1000) as ri:
        inp.first.press("Enter")
    if ri.value.status == 541: raise Blocked("541 on store search")
    log.info("search answered in %.1fs", time.time() - t0)
    try:
        page.locator('input[type="radio"][value^="R"]').first.wait_for(timeout=t * 1000)
    except PWTimeout:
        if _delivery_only(page): raise DeliveryOnly("no store list after search")
        raise
    time.sleep(0.5)

_last_trigger_ts = 0.0
def _peek_trigger_ts() -> float:
    try: return float(json.loads(TRIGGER.read_text()).get("ts", 0)) if TRIGGER.exists() else 0.0
    except Exception: return 0.0

def _read_trigger() -> dict | None:
    """Return a trigger newer than the last one we saw. The file is left in place so a second instance can read it too."""
    global _last_trigger_ts
    if not TRIGGER.exists(): return None
    try: d = json.loads(TRIGGER.read_text())
    except Exception: return None
    ts = float(d.get("ts", 0))
    if ts <= _last_trigger_ts: return None
    _last_trigger_ts = ts
    return d

def _launch(p, cfg, fresh: bool):
    prof = Path(cfg["checkout"]["chrome_profile_dir"])
    if fresh and prof.exists():
        keep = prof.with_name(prof.name + "-blocked-" + time.strftime("%m%d-%H%M"))
        shutil.move(str(prof), str(keep)); log.warning("fresh Chrome profile; old one kept at %s", keep.name)
    ctx = p.chromium.launch_persistent_context(str(prof), channel="chrome", headless=False,
        viewport={"width": 1280, "height": 1000}, ignore_default_args=["--enable-automation"], args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page(); page.set_default_timeout(cfg["checkout"]["timeout_seconds"] * 1000)
    return ctx, page

def run(cfg, notifier, lock, once=False) -> int:
    t = cfg["checkout"]["timeout_seconds"]; stores = cfg["pickup"]["stores"]; poll = cfg["polling"]
    preferred = cfg["product"]["variants"][0]
    hot_seconds = poll.get("hot_seconds", 25); rebuild_after = poll.get("session_rebuild_minutes", 17) * 60
    cooldown = poll.get("block_cooldown_seconds", 240); cool_max = poll.get("block_cooldown_max_seconds", 1800); blocks = 0
    with sync_playwright() as p:
        ctx, page = _launch(p, cfg, fresh=False)
        last = None; failures = 0; need_entry = True; entered_at = 0.0; hot_until = 0.0; trig_src = None
        try:
            while True:
                if plan.remaining(cfg, lock) == 0:
                    notifier.send(f"All {cfg['product']['want_total']} devices ordered. Bot stopping."); return 0
                if lock.has_unconfirmed():
                    log.error("unconfirmed order in ledger; bot paused"); return 3
                try:
                    trig = _read_trigger()
                    if trig and trig.get("avail"):
                        trig_src = trig.get("source", "watcher"); hot_until = time.time() + hot_seconds
                        log.info("trigger from %s: %s -> hot for %ss", trig_src, trig.get("avail"), hot_seconds)
                    if need_entry or "Fulfillment" not in page.url or time.time() - entered_at > rebuild_after:
                        if not need_entry and entered_at: log.info("rebuilding checkout session (age %.0f min)", (time.time() - entered_at) / 60)
                        _to_fulfillment(page, cfg, t, preferred); need_entry = False; entered_at = time.time()
                    _search(page, cfg, t)   # always refresh the session's store list first (0.5s warm); select on a stale list is rejected
                    states = _store_states(page, stores); failures = 0; blocks = 0
                    if not states or page.locator(':text("only eligible for delivery")').count():
                        # Apple flipped the parked session to delivery-only / an empty store list: it can't buy from here. Rebuild now.
                        log.warning("parked session shows no pickup stores (delivery-only flip); rebuilding checkout session")
                        need_entry = True; continue
                    summary = {k: v["available"] for k, v in states.items()}
                    if summary != last: log.info("browser status (%s): %s", preferred["part_number"], {k: v["label"] for k, v in states.items()}); last = summary
                    avail = {st: {preferred["part_number"]: v["available"]} for st, v in states.items()}
                    if trig and trig.get("avail") and trig.get("source") == "proxy_poller" and time.time() - float(trig.get("ts", 0)) < 30:
                        for st, parts in trig["avail"].items():
                            for pt, ok in parts.items():
                                if ok and pt not in avail.get(st, {}): avail.setdefault(st, {})[pt] = True
                    choice = plan.choose(cfg, lock, avail)
                    if choice:
                        store, part, qty = choice; variant = plan.variant(cfg, part)
                        log.info("BUYING %s at %s", variant['expected_title'], stores[store])
                        try:
                            staged = part == preferred["part_number"] and qty == 1 and "Fulfillment" in page.url
                            co.buy(page, cfg, store, variant, qty, notifier, lock, t, staged=staged)
                        except co.Abort as e:
                            co.shot(page, "attempt_abort"); log.error("attempt abort: %s", e)
                            # Retarget: Apple often bounces a lost checkout back to the store list with ANOTHER of our stores
                            # showing available for the same item. Take it immediately instead of restaging from the bag.
                            hops = 0
                            while hops < 2 and part == preferred["part_number"] and "Fulfillment" in page.url:
                                hops += 1
                                try:
                                    if "Fulfillment" in page.url: _search(page, cfg, t)   # refresh the list; the DOM is stale after XHR steps
                                    alt = {st: v["available"] for st, v in _store_states(page, stores).items()}
                                except Exception: alt = {}
                                nxt = next((st for st, ok in alt.items() if ok and st != store), None) or next((st for st, ok in alt.items() if ok), None)
                                if not nxt: break
                                log.info("RETARGET: %s shows available on the same page; buying there now", stores[nxt])
                                try:
                                    co.buy(page, cfg, nxt, variant, qty, notifier, lock, t, staged=True); store = nxt; e = None; break
                                except co.Abort as e2:
                                    co.shot(page, "attempt_abort"); log.error("retarget abort: %s", e2); store = nxt; e = e2
                            if e is not None: notifier.send(f"❌ Bot lost it at {stores[store]} ({str(e)[:60]}). Still watching.")
                        # After a loss Apple usually leaves us on the Fulfillment page with the staged bag intact: keep that
                        # session (saves add-to-bag + checkout + pickup-tab calls against the per-IP budget). Rebuild only if
                        # we swapped the bag or the page moved on.
                        need_entry = not (part == preferred["part_number"] and "Fulfillment" in page.url) or _delivery_only(page)
                        if not need_entry: log.info("staying on the parked session after the loss (no rebuild)")
                        else: log.info("rebuilding after the loss (page=%s, delivery-only=%s)", page.url[-40:], _delivery_only(page))
                        hot_until = time.time() + hot_seconds
                        continue
                except co.NeedsHuman as e:
                    notifier.send(f"NEEDS YOU: {e}", co.shot(page, "needs_human")); return 3
                except DeliveryOnly as e:
                    # Seen 2026-11-01 21:05: after a lost attempt Apple shows "Your order is only eligible for delivery" with no
                    # store list; waiting 3x25s for radios before rebuilding cost us the next flash. Rebuild immediately.
                    log.warning("parked session flipped to delivery-only (%s); rebuilding checkout session now", e)
                    need_entry = True; continue
                except Blocked as e:
                    blocks += 1; wait = min(cooldown * (2 ** (blocks - 1)), cool_max)
                    log.warning("BLOCKED (%s): %s. Silent for %ss, then re-enter%s.", blocks, e, wait, " on a fresh profile" if blocks >= 3 else "")
                    if blocks == 3: notifier.send(f"⚠️ Bot blocked by Apple (541) three times in a row; quiet {wait}s. Poller alerts still work.")
                    try: ctx.close()
                    except Exception: pass
                    time.sleep(wait)
                    # Apple's shield block sticks to the Chrome profile (a fresh guest profile passes while the old one
                    # stays blocked), so after 3 consecutive blocks start over on a fresh profile.
                    ctx, page = _launch(p, cfg, fresh=(blocks >= 3)); need_entry = True; last = None; failures = 0
                    continue
                except Exception as e:
                    failures += 1; log.warning("browser poll error (%s) at %s: %s", failures, page.url, str(e)[:200]); co.shot(page, "browser_poll_err")
                    if "/shop/404" in page.url:
                        blocks += 1; wait = min(cooldown * (2 ** (blocks - 1)), cool_max)
                        log.warning("BLOCKED (%s) via 404 page. Silent for %ss, then re-enter%s.", blocks, wait, " on a fresh profile" if blocks >= 3 else "")
                        try: ctx.close()
                        except Exception: pass
                        time.sleep(wait); ctx, page = _launch(p, cfg, fresh=(blocks >= 3)); need_entry = True; last = None; failures = 0
                        continue
                    if failures >= 3: need_entry = True; time.sleep(poll.get("failure_retry_seconds", 5))
                    if failures >= 6: log.warning("6+ consecutive failures; pausing %ss", poll.get("failure_pause_seconds", 120)); time.sleep(poll.get("failure_pause_seconds", 120))
                if once: return 0
                if time.time() < hot_until:
                    continue  # hot: next search immediately (Apple serialises them server-side; keep one queued)
                deadline = time.time() + poll["interval_seconds"] + random.uniform(0, poll["jitter_seconds"])
                while time.time() < deadline:
                    if _peek_trigger_ts() > _last_trigger_ts: break   # a new watcher trigger (compare the JSON ts, not mtime)
                    time.sleep(1)
        finally:
            try: ctx.close()
            except Exception: pass
