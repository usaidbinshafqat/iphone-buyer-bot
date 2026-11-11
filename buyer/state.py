"""Purchase ledger. Records every order attempt BEFORE Place Order is clicked, so a crash can never double-buy."""
import json, os, time
from pathlib import Path

class PurchaseLock:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict:
        if not self.path.exists():
            return {"orders": []}
        d = json.loads(self.path.read_text())
        if "orders" not in d:  # migrate old single-lock format
            d = {"orders": [dict(d, phase=d.get("phase", "submitted"))]}
        return d

    def _write(self, d):
        tmp = self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(d, indent=2)); os.replace(tmp, self.path)

    def start_order(self, part: str, qty: int, store: str, total: float) -> int:
        d = self.read(); oid = len(d["orders"])
        d["orders"].append({"id": oid, "part": part, "qty": qty, "store": store, "total": total, "phase": "submitting", "ts": time.time()})
        self._write(d); return oid

    def finish_order(self, oid: int, phase: str, order_number=None, note=None):
        d = self.read(); o = d["orders"][oid]
        o.update({"phase": phase, "order": order_number, "note": note, "updated": time.time()}); self._write(d)

    # ---- queries ----
    def counts(self) -> dict:
        """units per part counted from confirmed AND unconfirmed (submitting/submitted) orders — conservative."""
        c = {}
        for o in self.read()["orders"]:
            if o["phase"] in ("confirmed", "submitted", "submitting"):
                c[o["part"]] = c.get(o["part"], 0) + o["qty"]
        return c

    def has_unconfirmed(self) -> bool:
        """True only for an order that needs a human: Place Order clicked with no confirmation detected ("submitted"), or a
        "submitting" entry stuck for >3 min. A fresh "submitting" entry is the OTHER instance mid-Place-Order (≤60 s) — not a reason to pause."""
        now = time.time()
        for o in self.read()["orders"]:
            if o["phase"] == "submitted": return True
            if o["phase"] == "submitting" and now - float(o.get("ts", now)) > 180: return True
        return False

    def total_units(self) -> int:
        return sum(self.counts().values())

    # legacy API used by main/poller
    def is_locked(self) -> bool:
        return self.has_unconfirmed()
