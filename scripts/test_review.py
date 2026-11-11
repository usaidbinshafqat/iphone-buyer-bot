"""Dry run of checkout.buy() with an in-stock iPhone 17 as guest, qty from argv. Stops at Place Order. Clears the bag after."""
import sys, time, re, logging
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
from buyer import config, checkout, state
from buyer.notify import Notifier
from playwright.sync_api import sync_playwright
qty = int(sys.argv[1]) if len(sys.argv) > 1 else 1
cfg = config.load(); cfg["checkout"]["dry_run"] = True; cfg["notify"]["telegram_enabled"] = False
variant = {"part_number": "MG464LL/A", "expected_title": "iPhone 17 256GB Black", "max_units": 2,
           "product_url": "https://www.apple.com/shop/buy-iphone/iphone-17/6.3-inch-display-256gb-black-unlocked",
           "configurator_clicks": ["choose-noTradeIn", "purchaseGroupOptionfullprice", "carrierModelUNLOCKED/US", "noapplecare"]}
lock = state.PurchaseLock(config.ROOT / "state" / "scratch.lock.json")
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome", headless=False,
        viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page(); page.set_default_timeout(25000)
    try:
        r = checkout.buy(page, cfg, "R090", variant, qty, Notifier(cfg), lock, 25); print("RESULT:", r)
    finally:
        page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
        while page.locator('[data-autom="bag-item-remove-button"]').count():
            page.locator('[data-autom="bag-item-remove-button"]').first.click(); time.sleep(3)
        print("scratch bag cleared"); ctx.close()
