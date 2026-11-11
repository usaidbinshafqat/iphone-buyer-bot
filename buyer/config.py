import os, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def load(path=None):
    p = Path(path) if path else ROOT / "config.yaml"
    with open(p) as f:
        cfg = yaml.safe_load(f)
    for key in ("lock_file", "last_status_file"):
        cfg["state"][key] = os.path.expanduser(cfg["state"][key])
    cfg["checkout"]["chrome_profile_dir"] = os.path.expanduser(cfg["checkout"]["chrome_profile_dir"])
    return cfg
