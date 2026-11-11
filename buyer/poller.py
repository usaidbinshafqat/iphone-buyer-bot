"""Secondary HTTP poller routed through a SOCKS proxy (Tailscale exit node on a phone).
On availability it writes state/trigger.json, which the browser monitor picks up within ~2s."""
import json, logging, logging.handlers, random, sys, time
from pathlib import Path
import httpx
from . import config, monitor, secrets, state
from .notify import Notifier

def main():
    cfg = config.load(); root = config.ROOT
    (root / "logs").mkdir(exist_ok=True)
    h = logging.handlers.RotatingFileHandler(root / "logs" / "poller.log", maxBytes=5_000_000, backupCount=3)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=[h, logging.StreamHandler(sys.stdout)])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    log = logging.getLogger("poller")
    pc = cfg["polling"].get("proxy_poller", {})
    proxy = pc.get("proxy", "socks5://localhost:1055")
    if proxy == "keychain":  # rotating residential gateway; credentials in Keychain (proxy_user / proxy_pass)
        svc = cfg["notify"]["keychain_service"]
        user, pw = secrets.get(svc, "proxy_user"), secrets.get(svc, "proxy_pass")
        if not (user and pw): log.error("proxy=keychain but proxy_user/proxy_pass missing"); return 1
        proxy = f"http://{user}{pc.get('user_suffix', '')}:{pw}@{pc.get('gateway', 'gw.dataimpulse.com:823')}"
    rotating = pc.get("rotating", False)
    interval, jitter = pc.get("interval_seconds", 70), pc.get("jitter_seconds", 20)
    trigger = root / "state" / "trigger.json"
    notifier = Notifier(cfg); stores = cfg["pickup"]["stores"]
    lock = state.PurchaseLock(root / "state" / "purchase.lock.json")
    variants = {v["part_number"]: v for v in cfg["product"]["variants"]}; parts = list(variants)
    def new_client(): return httpx.Client(timeout=15, proxy=proxy, headers={"Connection": "close"})
    client = new_client()
    try:
        ip = client.get("https://api.ipify.org", headers={"User-Agent": "curl/8"}).text.strip()
        log.info("poller exit ip via %s: %s (rotating=%s, every %ss)", proxy.split("@")[-1], ip, rotating, interval)
    except Exception as e:
        log.error("proxy not working (%s); exiting so launchd restarts us", e); return 1
    backoff = 0; last = None; soft = 0; last_alert = {}
    while True:
        try:
            if rotating: client = new_client()   # fresh connection -> fresh exit IP on a per-request gateway
            res = monitor.check_many(parts, cfg["pickup"]["zip"], stores, client); backoff = 0; soft = 0
            summary = {st: {pt[:5]: v["pickup_display"] for pt, v in ps.items()} for st, ps in res.items()}
            if summary != last: log.info("status: %s", summary); last = summary
            avail = {st: {pt: bool(v["available"] and variants[pt]["expected_title"].lower() in (v["title"] or "").lower())
                          for pt, v in ps.items()} for st, ps in res.items()}
            store_parts = cfg["pickup"].get("store_parts", {}) or {}
            hits = [(st, pt) for st, ps in avail.items() for pt, ok in ps.items() if ok and (st not in store_parts or pt in store_parts[st])]
            # don't ping for variants we already have enough of (e.g. Star White after its max_units=1 was bought)
            counts = lock.counts(); done_all = lock.total_units() >= cfg["product"]["want_total"]
            hits = [] if done_all else [h for h in hits if counts.get(h[1], 0) < variants[h[1]].get("max_units", 99)]
            # alert on every NEW (store, part) immediately; re-alert the same ones only after 45s. Never stop polling.
            now = time.time(); new_hits = [h for h in hits if now - last_alert.get(h, 0) > 45]
            for h in new_hits: last_alert[h] = now
            hits = new_hits
            if hits:
                trigger.write_text(json.dumps({"ts": time.time(), "avail": avail, "source": "proxy_poller"}))
                ideal = [st for st, pt in hits if pt == "MK1H4LL/A"]
                others = " | ".join(f"{stores[st].upper()}: {variants[pt]['expected_title'].replace('iPhone Duo ', '')}" for st, pt in hits if pt != "MK1H4LL/A")
                if ideal:
                    where = " + ".join(stores[st].upper() for st in ideal)
                    for i in range(5):   # five back-to-back pings so the phone can't be missed
                        notifier.send(f"GO GO GO ({i + 1}/5)\n512 NIGHT SKY\n{where}\nhttps://www.apple.com/shop/bag")
                if others:
                    notifier.send("🟢 " + others + "\nhttps://www.apple.com/shop/bag")
                pass  # keep polling at full cadence; the browser debounces triggers itself
        except monitor.RateLimited as e:
            if rotating:  # that exit IP was hot; the next request gets another one
                soft += 1; log.warning("rate limited on this exit IP (%s); %s in a row, retrying", e, soft)
                backoff = 0 if soft < 5 else 60
            else:
                backoff = min(1800, max(600, backoff * 2)); log.warning("rate limited via proxy (%s); backoff %ss", e, backoff)
        except Exception as e:
            if rotating:  # a bad residential exit (TLS failure, dropped connection): just take the next IP
                soft += 1; backoff = 2 if soft < 10 else 60
                log.warning("poll error on this exit IP: %s; %s in a row, next IP in %ss", str(e)[:100], soft, backoff)
                if soft in (10, 30, 60):  # single exits fail often; 10 in a row means the proxy itself (quota/auth) is the problem
                    log.error("PROXY DOWN? %s consecutive poll failures via the proxy (data plan exhausted or auth rejected?): %s", soft, str(e)[:120])
            else:
                backoff = min(900, max(60, backoff * 2)); log.warning("poll error: %s; backoff %ss", str(e)[:150], backoff)
        time.sleep(backoff or interval + random.uniform(0, jitter))

if __name__ == "__main__":
    sys.exit(main())
