import sys, time, re, logging
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
from buyer import config, checkout
from playwright.sync_api import sync_playwright
cfg = config.load(); cfg["contact"]["phone"] = "5035550100"
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome", headless=False,
        viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page(); page.set_default_timeout(25000)
    page.on("response", lambda r: print("XHR", r.status, r.request.method, r.url[:140]) if "checkoutx" in r.url else None)
    page.on("dialog", lambda d: print("DIALOG", d.message))
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
    checkout.go_checkout(page, 25); time.sleep(3); print("URL:", page.url)
    if "Fulfillment" in page.url:
        checkout.select_pickup(page, cfg, "R090", 25); checkout.pickup_contact(page, cfg, 25)
    try: checkout.payment(page, cfg, 25)
    except Exception as e: print("payment():", str(e)[:150])
    print("URL now:", page.url)
    btn = page.locator('[data-autom="continue-button-review"]').first
    print("continue box:", btn.bounding_box(), "enabled:", btn.is_enabled())
    btn.scroll_into_view_if_needed(); btn.click(); 
    for i in range(12):
        time.sleep(2); print(i, page.url)
        if "Review" in page.url: break
    page.screenshot(path="state/discover/62_after_continue.png", full_page=True)
    print(page.locator("body").inner_text()[200:1500])
    ctx.close()
