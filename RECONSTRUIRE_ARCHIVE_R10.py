from __future__ import annotations

import base64
import hashlib
from pathlib import Path

BASE = "neutral_screen_v2_12_3_R10_github_audit.zip.b64.part-"
EXPECTED_SHA256 = "612bb8639b0da7824cca0efd0da48e3fdef6081f5f39953f05a2c6a5676a1790"

parts = sorted(Path("SOURCE_ARCHIVE_PARTS").glob(f"{BASE}*"))
if not parts:
    raise SystemExit("Aucune partie trouvée dans SOURCE_ARCHIVE_PARTS")

encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
data = base64.b64decode(encoded, validate=True)
out = Path("neutral_screen_v2_12_3_R10_github_audit.zip")
out.write_bytes(data)
actual = hashlib.sha256(data).hexdigest()
print(f"Archive créée : {out}")
print(f"SHA-256 : {actual}")
if actual != EXPECTED_SHA256:
    raise SystemExit("ERREUR : SHA-256 incorrect")
print("Intégrité OK")
