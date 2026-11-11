"""Exercise the REAL select_pickup/pickup_contact code as a guest on the scratch bag, then dump the payment page. No order."""
import sys, time, re, logging, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO)
from buyer import config, checkout
from playwright.sync_api import sync_playwright
exec(open(config.ROOT / "scripts" / "discover.py").read().split("with sync_playwright()")[0].split("cfg = config.load()")[1])
cfg = config.load(); cfg["contact"] = {"first_name": "Test", "last_name": "Discovery", "email": "you@example.com", "phone": "5035550100"}
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome", headless=False,
        viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page(); page.set_default_timeout(25000)
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
    page.locator('[data-autom="checkout"]').first.click(); time.sleep(5)
    g = page.locator('[data-autom="guest-checkout-btn"]')
    if g.count(): g.first.click()
    page.wait_for_url(re.compile("checkout"), timeout=60000); time.sleep(4)
    checkout.select_pickup(page, cfg, "R090", 25)
    checkout.pickup_contact(page, cfg, 25)
    time.sleep(4); print("URL:", page.url)
    page.locator('[data-autom="checkout-billingOptions-CREDIT"]').first.check(force=True); time.sleep(3)
    dump(page, "41_credit_fields")
    page.locator('[data-autom="continue-button-review"]').first.click(); time.sleep(4)
    dump(page, "42_credit_validation"); print(page.locator("body").inner_text()[300:2500])
    ctx.close()
