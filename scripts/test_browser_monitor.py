import sys, logging
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
from buyer import config, browser_monitor, state
from buyer.notify import Notifier
cfg = config.load(); cfg["checkout"]["chrome_profile_dir"] = str(config.ROOT / "state" / "scratch-profile")
cfg["contact"] = {"first_name": "Test", "last_name": "Discovery", "email": "you@example.com", "phone": "5035550100"}
lock = state.PurchaseLock(config.ROOT / "state" / "scratch.lock.json")
sys.exit(browser_monitor.run(cfg, Notifier(cfg), lock, once=True))
