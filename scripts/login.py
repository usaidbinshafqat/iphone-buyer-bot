"""Open the persistent Chrome profile so you can sign in to apple.com once (and trust the browser)."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from buyer import config
from playwright.sync_api import sync_playwright

cfg = config.load()
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        cfg["checkout"]["chrome_profile_dir"], channel="chrome", headless=False,
        viewport={"width": 1280, "height": 900}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://secure.apple.com/shop/sign_in")
    print("Sign in to your Apple account in the window, tick 'Trust this browser' on the 2FA step,")
    print("then open https://www.apple.com/shop/bag to confirm the Duo is in the bag. Press Enter here when done.")
    input()
    ctx.close()
