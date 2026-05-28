"""
Machine fingerprinting for node-locked licensing.
Generates a stable ID from hardware identifiers.
"""
import hashlib
import platform
import uuid
import socket


def get_machine_id() -> str:
    """Return a stable 16-char hex ID unique to this machine."""
    parts = [
        platform.node(),                          # hostname
        str(uuid.getnode()),                      # MAC address as int
        platform.machine(),                       # x86_64 etc
        platform.processor(),                     # CPU string
        socket.gethostname(),                     # FQDN hostname
    ]
    raw = "|".join(p for p in parts if p)
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def get_machine_label() -> str:
    """Human-readable machine description for display."""
    return f"{platform.node()} ({platform.system()} {platform.release()})"


if __name__ == "__main__":
    mid = get_machine_id()
    label = get_machine_label()
    print(f"Machine ID : {mid}")
    print(f"Label      : {label}")
