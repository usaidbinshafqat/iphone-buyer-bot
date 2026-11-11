import sys, json, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from buyer import config
from playwright.sync_api import sync_playwright
exec(open(config.ROOT / "scripts" / "discover.py").read().split("with sync_playwright()")[0].split("cfg = config.load()")[1])  # reuse dump()
cfg = config.load()

def click(page, autom, **kw):
    loc = page.locator(f'[data-autom="{autom}"]').first
    loc.scroll_into_view_if_needed(); loc.click(force=True, **kw); time.sleep(1.2)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome",
        headless=False, viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(cfg["product"]["product_url"], wait_until="domcontentloaded"); time.sleep(4)
    for a in ["dimensionColornightsky","dimensionCapacity512gb","choose-noTradeIn","purchaseGroupOptionfullprice","carrierModelUNLOCKED/US","noapplecare"]:
        try: click(page, a)
        except Exception as e: print("click fail", a, e)
    time.sleep(2); dump(page, "02_configured")
    summary = page.locator('[data-autom="add-to-cart"]').first
    print("add-to-cart enabled:", summary.is_enabled())
    click(page, "add-to-cart"); time.sleep(4); dump(page, "03_after_add")
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(4); dump(page, "04_bag")
    # proceed to checkout
    for a in ["checkout", "proceed"]:
        if page.locator(f'[data-autom="{a}"]').count(): click(page, a); break
    time.sleep(5); dump(page, "05_checkout_signin")
    g = page.locator('[data-autom="guest-checkout-btn"]')
    if g.count(): g.first.click(); time.sleep(6); dump(page, "06_fulfillment")
    else: print("no guest button found")
    ctx.close()
