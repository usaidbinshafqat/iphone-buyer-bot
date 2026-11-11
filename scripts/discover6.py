"""Learn pickup-details / payment pages using an in-stock iPhone 17 as a GUEST. Never places an order."""
import sys, json, time, re
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from buyer import config
from playwright.sync_api import sync_playwright
exec(open(config.ROOT / "scripts" / "discover.py").read().split("with sync_playwright()")[0].split("cfg = config.load()")[1])
cfg = config.load()
def first(page, sel):
    el = page.locator(sel).first; el.scroll_into_view_if_needed(); el.click(force=True); time.sleep(0.8)
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome", headless=False,
        viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("response", lambda r: print("XHR", r.status, r.request.method, r.url[:150]) if "secure" in r.url and r.request.resource_type in ("xhr","fetch") and "checkoutx" in r.url else None)
    # clear scratch bag
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
    while page.locator('[data-autom="bag-item-remove-button"]').count():
        page.locator('[data-autom="bag-item-remove-button"]').first.click(); time.sleep(3)
    page.goto("https://www.apple.com/shop/buy-iphone/iphone-17/6.3-inch-display-256gb-black-unlocked", wait_until="domcontentloaded"); time.sleep(4)
    for sel in [
                '[data-autom="choose-noTradeIn"]', '[data-autom="purchaseGroupOptionfullprice"]', '[data-autom="carrierModelUNLOCKED/US"]', '[data-autom="noapplecare"]']:
        try: first(page, sel)
        except Exception as e: print("skip", sel, str(e)[:60])
    time.sleep(1); first(page, '[data-autom="add-to-cart"]'); time.sleep(5)
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
    print("bag:", page.locator('[data-autom="bag-item-name"]').all_inner_texts())
    page.locator('[data-autom="checkout"]').first.click(); time.sleep(5)
    g = page.locator('[data-autom="guest-checkout-btn"]')
    if g.count(): g.first.click()
    page.wait_for_url(re.compile("checkout"), timeout=60000)
    page.get_by_text(re.compile("pick it up")).first.wait_for(timeout=60000); time.sleep(1)
    page.get_by_text(re.compile("pick it up")).first.click(); time.sleep(3)
    inp = page.locator('[data-autom="bag-storelocator-input"]')
    if not (inp.count() and inp.first.is_visible()):
        page.locator('[data-autom="fulfillment-pickup-store-search-button"]').first.click(); time.sleep(1.5)
        inp = page.locator('[data-autom="bag-storelocator-input"]')
    inp.first.fill("97223"); inp.first.press("Enter")
    page.locator('input[type="radio"][value^="R"]').first.wait_for(timeout=60000); time.sleep(3)
    radios = page.locator('input[type="radio"][value^="R"]')
    chosen = None
    for i in range(radios.count()):
        r = radios.nth(i); lab = r.locator("xpath=ancestor::*[self::label or self::div][1]").inner_text()
        print("store", r.get_attribute("value"), lab.replace("\n"," | ")[:120])
        if chosen is None and not re.search("unavailable", lab, re.I): chosen = r
    if chosen is None: print("NO STORE AVAILABLE"); ctx.close(); sys.exit()
    chosen.check(force=True); time.sleep(1); dump(page, "20_store_selected")
    page.locator('[data-autom="fulfillment-continue-button"]').click(); time.sleep(6)
    dump(page, "21_pickup_details"); print(page.locator("body").inner_text()[300:3500])
    # press continue with nothing filled to surface required fields
    btn = page.locator('button[data-autom*="continue"]:visible')
    print("continue buttons:", [btn.nth(i).get_attribute("data-autom") for i in range(btn.count())])
    if btn.count(): btn.first.click(); time.sleep(4); dump(page, "22_pickup_details_validation"); print(page.locator("body").inner_text()[300:3000])
    ctx.close()
