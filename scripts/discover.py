"""Map Apple's configurator/bag/checkout DOM as a guest using a scratch profile. Never places orders."""
import sys, json, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from buyer import config
from playwright.sync_api import sync_playwright

cfg = config.load()
OUT = config.ROOT / "state" / "discover"; OUT.mkdir(parents=True, exist_ok=True)

def dump(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    els = page.evaluate("""() => [...document.querySelectorAll('button,a[href],input,select,[role=radio],[role=button],fieldset')]
      .filter(e => e.offsetParent !== null)
      .map(e => ({tag:e.tagName, type:e.type||null, id:e.id||null, name:e.name||null, text:(e.innerText||e.value||e.getAttribute('aria-label')||'').trim().slice(0,80), cls:(e.className||'').toString().slice(0,80), testid:e.getAttribute('data-autom')}))""")
    (OUT / f"{name}.json").write_text(json.dumps(els, indent=1))
    print(f"--- {name}: {page.url}  ({len(els)} elements)")
    for e in els:
        if e["text"] or e["testid"]:
            print(f"  {e['tag']:8} {e['type'] or '':8} autom={e['testid']!s:40} {e['text']!r}")

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / "state" / "scratch-profile"), channel="chrome",
        headless=False, viewport={"width": 1280, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(cfg["product"]["product_url"], wait_until="domcontentloaded"); time.sleep(4)
    dump(page, "01_configurator")
    ctx.close()
