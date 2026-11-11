"""Main loop: poll inventory, trigger checkout on availability, stop after one purchase."""
import argparse, json, logging, logging.handlers, random, sys, time
from pathlib import Path
import httpx
from . import config, monitor, state
from .notify import Notifier

def setup_logging(root: Path, name: str = "buyer"):
    (root / "logs").mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    h = logging.handlers.RotatingFileHandler(root / "logs" / f"{name}.log", maxBytes=5_000_000, backupCount=5)
    h.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[h, sh])
    logging.getLogger("httpx").setLevel(logging.WARNING)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="poll once and exit")
    ap.add_argument("--force-checkout", metavar="STORE", help="skip inventory check and run checkout for STORE (dry-run testing)")
    ap.add_argument("--browser", action="store_true", help="use the checkout-page store search instead of the HTTP endpoint")
    ap.add_argument("--part", help="with --force-checkout: part number (default preferred variant)")
    ap.add_argument("--qty", type=int, default=1, help="with --force-checkout: quantity")
    args = ap.parse_args()

    cfg = config.load()
    # Optional env overrides so a second instance can park a different variant in its own Chrome profile:
    #   BUYER_PARTS=MK1F4LL/A[,...]  BUYER_PROFILE_DIR=/path  BUYER_LOG_NAME=buyer-b  BUYER_INTERVAL=180
    import os
    if os.environ.get("BUYER_PARTS"):
        keep = [x.strip() for x in os.environ["BUYER_PARTS"].split(",") if x.strip()]
        cfg["product"]["variants"] = [v for v in cfg["product"]["variants"] if v["part_number"] in keep]
    if os.environ.get("BUYER_PROFILE_DIR"): cfg["checkout"]["chrome_profile_dir"] = os.environ["BUYER_PROFILE_DIR"]
    if os.environ.get("BUYER_INTERVAL"): cfg["polling"]["interval_seconds"] = int(os.environ["BUYER_INTERVAL"])
    setup_logging(config.ROOT, os.environ.get("BUYER_LOG_NAME", "buyer"))
    log = logging.getLogger("main")
    notifier = Notifier(cfg)
    lock = state.PurchaseLock(cfg["state"]["lock_file"])
    variants = {v["part_number"]: v for v in cfg["product"]["variants"]}; parts = list(variants)
    stores = cfg["pickup"]["stores"]
    poll = cfg["polling"]

    from . import plan
    if lock.has_unconfirmed():
        log.error("unconfirmed order in ledger (%s). Bot paused until you edit it.", lock.path)
        notifier.send("apple-buyer: unconfirmed order in ledger, bot paused. Verify at apple.com/orders and edit state/purchase.lock.json.")
        return 0
    if plan.remaining(cfg, lock) == 0:
        log.info("all %s devices ordered; nothing to do", cfg["product"]["want_total"]); return 0

    log.info("monitoring %s at %s every ~%ss (dry_run=%s, have %d/%d)", parts, list(stores), poll["interval_seconds"],
             cfg["checkout"]["dry_run"], lock.total_units(), cfg["product"]["want_total"])
    log.info("(quiet) " + f"apple-buyer started: {' / '.join(v['expected_title'] for v in variants.values())} @ {', '.join(stores.values())} "
                  f"(dry_run={cfg['checkout']['dry_run']}, have {lock.total_units()}/{cfg['product']['want_total']})")

    if args.force_checkout:
        from .checkout import run_checkout
        return run_checkout(cfg, args.force_checkout, notifier, lock, part=args.part, qty=args.qty)

    if args.browser or cfg["polling"].get("mode") == "browser":
        from . import browser_monitor
        return browser_monitor.run(cfg, notifier, lock, once=args.once)

    client = httpx.Client(timeout=15)
    consecutive_541 = 0
    backoff = 0
    last = {}
    status_file = Path(cfg["state"]["last_status_file"])
    while True:
        try:
            res = monitor.check_many(parts, cfg["pickup"]["zip"], stores, client)
            backoff = 0; consecutive_541 = 0
            summary = {st: {pt[:5]: v["pickup_display"] for pt, v in ps.items()} for st, ps in res.items()}
            if summary != last:
                log.info("status change: %s", summary); last = summary
            status_file.write_text(json.dumps({"ts": time.time(), "stores": res}, indent=2))
            avail = {st: {pt: bool(v["available"] and variants[pt]["expected_title"].lower() in (v["title"] or "").lower())
                          for pt, v in ps.items()} for st, ps in res.items()}
            choice = plan.choose(cfg, lock, avail)
            if choice:
                store, part, qty = choice
                notifier.send(f"IN STOCK: {variants[part]['expected_title']} at {stores[store]}. Starting checkout x{qty}.")
                from .checkout import run_checkout
                rc = run_checkout(cfg, store, notifier, lock, part=part, qty=qty)
                log.info("checkout rc=%s; have %d/%d", rc, lock.total_units(), cfg["product"]["want_total"])
                if lock.has_unconfirmed() or plan.remaining(cfg, lock) == 0:
                    return 0
        except monitor.RateLimited as e:
            consecutive_541 += 1
            backoff = min(poll["backoff_max_seconds"], max(600, backoff * 2))
            log.warning("rate limited (%s); backing off %ss", e, backoff)
            if consecutive_541 >= 2 and cfg["polling"].get("fallback_to_browser", True):
                log.warning("HTTP endpoint blocked; switching to browser monitor")
                notifier.send("apple-buyer: pickup endpoint blocked (541); switching to checkout-page monitoring")
                from . import browser_monitor
                return browser_monitor.run(cfg, notifier, lock, once=args.once)
        except Exception as e:
            backoff = min(poll["backoff_max_seconds"], max(60, backoff * 2))
            log.exception("poll error: %s; backing off %ss", e, backoff)
        if args.once:
            print(json.dumps(res, indent=2) if 'res' in dir() else "no result")
            return 0
        time.sleep(backoff or poll["interval_seconds"] + random.uniform(0, poll["jitter_seconds"]))

if __name__ == "__main__":
    sys.exit(main())
