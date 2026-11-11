import sys, time, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from buyer import config
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome", headless=False,
        viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    r = page.goto("https://www.apple.com/shop/buy-iphone/iphone-duo", wait_until="domcontentloaded")
    print("page status", r.status); time.sleep(3)
    for i in range(2):
        res = page.evaluate("""async () => { const r = await fetch('/shop/retail/pickup-message?pl=true&parts.0=MK1H4LL/A&location=97223', {headers:{'Accept':'application/json'}}); return {status:r.status, text:(await r.text()).slice(0,300)}; }""")
        print("in-page fetch:", res["status"], res["text"][:200]); time.sleep(5)
    ctx.close()
