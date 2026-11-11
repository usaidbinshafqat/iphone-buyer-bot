import logging, queue, threading, httpx
from . import secrets

log = logging.getLogger("notify")

class Notifier:
    """Telegram alerts. send() returns immediately: messages go through a background thread (in order), so an alert
    never adds latency to the checkout path."""
    def __init__(self, cfg):
        self.enabled = cfg["notify"]["telegram_enabled"]
        svc = cfg["notify"]["keychain_service"]
        self.token = secrets.get(svc, "telegram_bot_token") if self.enabled else None
        self.chat_id = secrets.get(svc, "telegram_chat_id") if self.enabled else None   # one id, or several comma-separated
        if self.enabled and not (self.token and self.chat_id):
            log.warning("telegram enabled but token/chat_id missing in Keychain; alerts disabled")
            self.enabled = False
        self._q: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="telegram", daemon=True); self._worker.start()

    def send(self, text: str, photo_path: str | None = None):
        log.info("ALERT: %s", text)
        if self.enabled:
            self._q.put((text, photo_path))

    def flush(self, timeout: float = 10.0):
        """Wait for queued alerts to go out (used before the process exits)."""
        try: self._q.join()
        except Exception: pass

    def _run(self):
        while True:
            text, photo_path = self._q.get()
            try: self._post(text, photo_path)
            except Exception as e: log.error("telegram send failed: %s", e)
            finally: self._q.task_done()

    def _post(self, text: str, photo_path: str | None):
        base = f"https://api.telegram.org/bot{self.token}"
        for chat_id in [c.strip() for c in str(self.chat_id).split(",") if c.strip()]:
            try:
                if photo_path:
                    with open(photo_path, "rb") as f:
                        httpx.post(f"{base}/sendPhoto", data={"chat_id": chat_id, "caption": text[:1000]}, files={"photo": f}, timeout=20)
                else:
                    httpx.post(f"{base}/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=20)
            except Exception as e:
                log.error("telegram send to %s failed: %s", chat_id, e)
