"""Store secrets in the macOS login Keychain. Nothing is echoed or logged."""
import getpass, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from buyer import secrets, config

cfg = config.load()
svc = cfg["notify"]["keychain_service"]
items = {
    "card_number": "Primary card number (digits only; blank to skip)",
    "card_exp": "Primary card expiration MM/YY (blank to skip)",
    "card_cvv": "Primary card security code / CVV (blank to skip)",
    "card2_number": "Backup card number, retried automatically if the primary is declined (blank to skip)",
    "card2_exp": "Backup card expiration MM/YY (blank to skip)",
    "card2_cvv": "Backup card security code / CVV (blank to skip)",
    "telegram_bot_token": "Telegram bot token (blank to skip)",
    "telegram_chat_id": "Telegram chat id, or several separated by commas (blank to skip)",
    "proxy_user": "Residential proxy username for the stock poller (blank to skip)",
    "proxy_pass": "Residential proxy password for the stock poller (blank to skip)",
}
for key, prompt in items.items():
    v = getpass.getpass(f"{prompt}: ").strip()
    if v:
        secrets.set_(svc, key, v)
        print(f"  stored {key}")
    else:
        print(f"  skipped {key}")
print("done. Verify with: security find-generic-password -s", svc, "-a card_cvv  (no -w, so it won't print the value)")
