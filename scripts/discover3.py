import sys, json, time, re
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from buyer import config
from playwright.sync_api import sync_playwright
exec(open(config.ROOT / "scripts" / "discover.py").read().split("with sync_playwright()")[0].split("cfg = config.load()")[1])
cfg = config.load()
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome",
        headless=False, viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
    page.locator('[data-autom="checkout"]').first.click(); time.sleep(5)
    g = page.locator('[data-autom="guest-checkout-btn"]')
    if g.count(): g.first.click()
    for i in range(30):
        time.sleep(2)
        print(i, page.url, page.locator('[data-autom="fulfillment-continue-button"]').count())
        if page.locator('[data-autom="fulfillment-continue-button"]').count(): break
    page.screenshot(path="state/discover/07_pre.png")
    dump(page, "07_fulfillment_again")
    btn = page.get_by_text(re.compile("pick it up"))
    print("pickup text matches:", btn.count())
    btn.first.click(); time.sleep(4); dump(page, "08_pickup_tab")
    z = page.locator('[data-autom="checkout-zipcode-edit"]')
    print("zip edit buttons:", z.count())
    if z.count():
        z.first.click(); time.sleep(2); dump(page, "09_zip_edit")
        inp = page.locator('input:visible').last
        inp.fill("97223"); inp.press("Enter"); time.sleep(5); dump(page, "10_pickup_97223")
    print(page.locator("body").inner_text()[:2500])
    ctx.close()
