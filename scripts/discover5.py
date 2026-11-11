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
    def on_resp(r):
        u = r.url
        if "secure" in u and r.request.resource_type in ("xhr","fetch"):
            print("XHR", r.status, r.request.method, u[:160])
    page.on("response", on_resp)
    page.goto("https://www.apple.com/shop/bag", wait_until="domcontentloaded"); time.sleep(3)
    page.locator('[data-autom="checkout"]').first.click(); time.sleep(5)
    g = page.locator('[data-autom="guest-checkout-btn"]')
    if g.count(): g.first.click()
    page.wait_for_url(re.compile("checkout"), timeout=60000)
    page.get_by_text(re.compile("pick it up")).first.wait_for(timeout=60000); time.sleep(1)
    page.get_by_text(re.compile("pick it up")).first.click(); time.sleep(3)
    page.locator('[data-autom="bag-storelocator-input"]').fill("97223"); time.sleep(1)
    page.locator('[data-autom="bag-storelocator-input"]').press("Enter")
    for i in range(20):
        time.sleep(3)
        t = page.locator("body").inner_text()
        if "Enter a zip code" not in t: break
    dump(page, "12_pickup_stores")
    print(page.locator("body").inner_text()[600:3500])
    ctx.close()
