import sys, json, time, re
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from buyer import config
from playwright.sync_api import sync_playwright
exec(open(config.ROOT / "scripts" / "discover.py").read().split("with sync_playwright()")[0].split("cfg = config.load()")[1])
cfg = config.load()
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome", headless=False,
        viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("response", lambda r: print("XHR", r.status, r.request.method, r.url[:150]) if "checkoutx" in r.url else None)
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
    print("bag:", page.locator('[data-autom="bag-item-name"]').all_inner_texts())
    page.locator('[data-autom="checkout"]').first.click(); time.sleep(5)
    g = page.locator('[data-autom="guest-checkout-btn"]')
    if g.count(): g.first.click()
    page.wait_for_url(re.compile("checkout"), timeout=60000)
    page.get_by_text(re.compile("pick it up")).first.wait_for(timeout=60000); time.sleep(1)
    page.get_by_text(re.compile("pick it up")).first.click(); time.sleep(3)
    btn = page.locator('[data-autom="fulfillment-pickup-store-search-button"]')
    if btn.count() and "97223" not in btn.first.inner_text():
        btn.first.click(); time.sleep(1); inp = page.locator('[data-autom="bag-storelocator-input"]'); inp.first.fill("97223"); inp.first.press("Enter")
    elif not btn.count():
        inp = page.locator('[data-autom="bag-storelocator-input"]'); inp.first.fill("97223"); inp.first.press("Enter")
    page.locator('input[type="radio"][value="R090"]').first.wait_for(timeout=60000); time.sleep(3)
    r = page.locator('input[type="radio"][value="R090"]').first
    print("R090 label:", r.locator("xpath=ancestor::*[self::label or self::div][1]").inner_text().replace("\n"," | "))
    r.check(force=True)
    page.locator('[data-autom="pickup-availablewindow-dropdown"]').first.wait_for(timeout=30000); time.sleep(1)
    dates = page.locator('fieldset:has-text("pickup date") input[type="radio"]')
    print("date enabled:", [dates.nth(i).is_enabled() for i in range(dates.count())])
    print("date radios:", dates.count(), [dates.nth(i).get_attribute("value") for i in range(dates.count())], "checked:", [dates.nth(i).is_checked() for i in range(dates.count())])
    for i in range(dates.count()):
        if dates.nth(i).is_enabled(): dates.nth(i).check(force=True); time.sleep(1.5); break
    sel = page.locator('[data-autom="pickup-availablewindow-dropdown"]')
    opts = sel.first.locator("option").all_inner_texts() if sel.count() else []
    print("window options:", opts[:5], "selected:", sel.first.input_value() if sel.count() else None)
    if sel.count():
        vals = [sel.first.locator("option").nth(i).get_attribute("value") for i in range(min(3, len(opts)))]
        print("option values:", vals)
        sel.first.select_option(index=1 if len(opts) > 1 and not vals[0] else 0); time.sleep(1.5)
    dump(page, "32_slot_selected")
    page.locator('[data-autom="fulfillment-continue-button"]').click(); time.sleep(7)
    dump(page, "33_after_slot"); print(page.locator("body").inner_text()[300:2500])
    # click continue again if still on fulfillment, then dump what it asks a guest for
    if page.locator('[data-autom="fulfillment-continue-button"]').count():
        page.locator('[data-autom="fulfillment-continue-button"]').click(); time.sleep(7); dump(page, "34_after_slot2"); print(page.locator("body").inner_text()[300:2000])
    ctx.close()
