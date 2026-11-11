"""Decide what to buy given availability. Preference order = config variants order (blue first)."""
import logging
log = logging.getLogger("plan")

def remaining(cfg, ledger) -> int:
    return max(0, cfg["product"]["want_total"] - ledger.total_units())

def variant(cfg, part):
    return next(v for v in cfg["product"]["variants"] if v["part_number"] == part)

def choose(cfg, ledger, avail: dict):
    """avail: {store: {part: True/False}}. Returns (store, part, qty) or None.
    Rules: never exceed want_total; never exceed each variant's max_units; prefer earlier variants; prefer more units."""
    rem = remaining(cfg, ledger)
    if rem == 0 or ledger.has_unconfirmed():
        return None
    counts = ledger.counts()
    best = None
    for rank, v in enumerate(cfg["product"]["variants"]):
        part = v["part_number"]
        cap = min(rem, v["max_units"] - counts.get(part, 0), cfg["product"].get("units_per_order", 1))
        if cap <= 0:
            continue
        store_order = list(cfg["pickup"]["stores"]); store_parts = cfg["pickup"].get("store_parts", {}) or {}
        for store, parts in avail.items():
            if store in store_parts and part not in store_parts[store]:
                continue   # this store is allow-listed to other parts only
            if parts.get(part):
                srank = store_order.index(store) if store in store_order else 99
                cand = (-cap, rank, srank, store, part, cap)   # more units first, then colour preference, then store order (config)
                if best is None or cand < best:
                    best = cand
    if best is None:
        return None
    _, _, _, store, part, qty = best
    log.info("plan: buy %s x%d at %s (remaining %d, counts %s)", part, qty, store, rem, counts)
    return store, part, qty
