import sys, time, re, logging
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
from buyer import config, checkout, secrets
from playwright.sync_api import sync_playwright
cfg = config.load(); cfg["contact"]["phone"] = "5035550100"
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome", headless=False,
        viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page(); page.set_default_timeout(25000)
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
    checkout.go_checkout(page, 25); time.sleep(3); print("URL:", page.url)
    if "Fulfillment" in page.url:
        checkout.select_pickup(page, cfg, "R090", 25); checkout.pickup_contact(page, cfg, 25)
    page.wait_for_url(re.compile("Billing")); time.sleep(2)
    page.locator('[data-autom="checkout-billingOptions-CREDIT"]').first.click(force=True); time.sleep(2)
    if not page.locator('[data-autom="card-number-input"]').first.is_visible():
        page.locator('[data-autom="continue-button-review"]').first.click(); time.sleep(2)
    cn = page.locator('[data-autom="card-number-input"]').first
    print("card input visible:", cn.is_visible(), "box:", cn.bounding_box())
    cn.scroll_into_view_if_needed(); cn.click(); time.sleep(0.5)
    print("focused:", page.evaluate("document.activeElement && document.activeElement.getAttribute('data-autom')"))
    page.keyboard.type("4111111111111111", delay=40); time.sleep(0.5)
    print("card value after type:", cn.input_value())
    page.screenshot(path="state/discover/60_card_typed.png", full_page=True)
    ex = page.locator('[data-autom="expiration-input"]').first; ex.click(); page.keyboard.type("0631", delay=40); time.sleep(0.3); print("exp:", ex.input_value())
    cv = page.locator('[data-autom="security-code-input"]').first
    print("cvv box:", cv.bounding_box(), "visible:", cv.is_visible())
    cv.scroll_into_view_if_needed(); cv.click(timeout=8000); page.keyboard.type("732", delay=40); print("cvv len:", len(cv.input_value()))
    page.screenshot(path="state/discover/61_card_done.png", full_page=True)
    ctx.close()
