"""Secrets live in the macOS login Keychain, never in files or logs."""
import subprocess

def get(service: str, account: str) -> str | None:
    r = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

def set_(service: str, account: str, value: str) -> None:
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", service, "-a", account, "-w", value],
        check=True, capture_output=True)
