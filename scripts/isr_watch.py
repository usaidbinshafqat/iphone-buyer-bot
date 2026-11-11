"""Second stock signal: poll InStock Radar's public US iPhone Duo page (server-rendered, per-store cards refreshed ~20s)
and drop state/trigger.json when one of our stores shows our part in stock. No Apple rate limit involved.
Run: PYTHONPATH=~/apple-buyer .venv/bin/python scripts/isr_watch.py"""
import html, json, logging, logging.handlers, random, re, sys, time
from pathlib import Path
import httpx
from buyer import config
from buyer.notify import Notifier

URL = "https://instockradar.com/us/iphone-duo"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"

def parse(page: str, stores: dict) -> dict:
    """{store: {"in_stock": bool, "text": str}} from the store cards (id="s-R090" ...)."""
    out = {}
    for st in stores:
        m = re.search(rf'id="s-{st}"', page)
        if not m: continue
        nxt = re.search(r'id="s-R\d+"', page[m.end():])
        chunk = page[m.start(): m.end() + (nxt.start() if nxt else 4000)]
        t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", chunk)))
        out[st] = {"in_stock": bool(re.search(r"\bIn stock\b", t)) and not re.search(r"\bSold out\b", t), "text": t[:300]}
    return out

def main():
    cfg = config.load(); root = config.ROOT
    h = logging.handlers.RotatingFileHandler(root / "logs" / "isr_watch.log", maxBytes=5_000_000, backupCount=2)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[h, logging.StreamHandler(sys.stdout)])
    logging.getLogger("httpx").setLevel(logging.WARNING); log = logging.getLogger("isr")
    stores = cfg["pickup"]["stores"]; variants = cfg["product"]["variants"]
    trigger = root / "state" / "trigger.json"; notifier = Notifier(cfg)
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    last = {}; backoff = 0; last_trigger = 0.0
    with httpx.Client(timeout=15, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, http2=False) as c:
        while True:
            try:
                r = c.get(URL)
                if r.status_code != 200: raise RuntimeError(f"HTTP {r.status_code}")
                states = parse(r.text, stores); backoff = 0
                summary = {st: v["in_stock"] for st, v in states.items()}
                if summary != last:
                    log.info("status: %s", {st: (v["text"][:110]) for st, v in states.items()}); last = summary
                avail = {}
                for st, v in states.items():
                    if not v["in_stock"]: continue
                    for var in variants:
                        m = re.match(r"iPhone Duo (\d+)(GB|TB) (.+)", var["expected_title"])   # e.g. "iPhone Duo 256GB Night Sky"
                        if not m: continue
                        cap, unit, colour = m.groups()
                        # InStock Radar lists "In stock 512 GB Night Sky" per card (one or more capacity/colour pairs)
                        if re.search(rf"{cap}\s*{unit}\s+{re.escape(colour)}", v["text"], re.I):
                            avail.setdefault(st, {})[var["part_number"]] = True
                if avail and time.time() - last_trigger > 20:
                    trigger.write_text(json.dumps({"ts": time.time(), "avail": avail, "source": "instockradar"}))
                    last_trigger = time.time()
                    log.info("TRIGGER %s", avail)
                    log.info("(quiet) InStock Radar hit %s", avail)
            except Exception as e:
                backoff = min(300, max(15, backoff * 2)); log.warning("error: %s; backoff %ss", str(e)[:120], backoff)
            time.sleep(backoff or interval + random.uniform(0, 2))

if __name__ == "__main__":
    main()
