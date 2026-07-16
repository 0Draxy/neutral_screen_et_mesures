from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PATCH_DIR = HERE / "patches"
SUPPORT_DIR = HERE / "support"

PATCHES = {
    "main": {
        "glob": "main.patch.part*",
        "source": ROOT / "main_ihm_relais_rp2040_v2_12_2.py",
        "target": ROOT / "main_ihm_relais_rp2040_v2_12_3.py",
        "sha256": "268492cde1ec7def1f5cc52fe136b1f0e26c2be27f561ddafecd7cd2c0221c98",
    },
    "ui": {
        "glob": "ui.patch.part*",
        "source": ROOT / "ihm_relais_rp2040_28vdc_precision_v2_12_2.ui",
        "target": ROOT / "ihm_relais_rp2040_28vdc_precision_v2_12_3.ui",
        "sha256": "188a0c725a3bbd1632d863d60d907d032e1ff62d146cb510d9c6a2b7ebf6d3e7",
    },
    "firmware": {
        "glob": "firmware.patch.part*",
        "source": ROOT / "rp2040_relais_28vdc_precision_v2_12_2_ADS1115_GP26_RGB.ino",
        "target": ROOT / "rp2040_relais_28vdc_precision_v2_12_3_ADS1115_GP26_RGB.ino",
        "sha256": "4dc604fcffbc257b0c5c4065bfff7c928809784e0efdad42b25d104c007e3a6a",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def combine(pattern: str, destination: Path) -> None:
    parts = sorted(PATCH_DIR.glob(pattern))
    if not parts:
        raise FileNotFoundError(f"Aucune partie trouvée pour {pattern}")
    with destination.open("wb") as output:
        for part in parts:
            output.write(part.read_bytes())


def apply_one(name: str, config: dict[str, object]) -> None:
    source = Path(config["source"])
    target = Path(config["target"])
    expected = str(config["sha256"])
    if not source.exists():
        raise FileNotFoundError(f"Source V2.12.2 absente : {source.name}")

    patch_file = HERE / f"_{name}.combined.patch"
    working = HERE / f"_{name}.work"
    combine(str(config["glob"]), patch_file)
    shutil.copy2(source, working)

    command = ["patch", "--batch", "--forward", "-p0", "-i", str(patch_file), str(working)]
    completed = subprocess.run(command, cwd=HERE, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Échec du patch {name}.\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )

    target.write_bytes(working.read_bytes())
    actual = sha256(target)
    if actual != expected:
        raise RuntimeError(
            f"SHA-256 incorrect pour {target.name}: attendu {expected}, obtenu {actual}"
        )
    patch_file.unlink(missing_ok=True)
    working.unlink(missing_ok=True)
    print(f"OK  {target.name}  {actual}")


def install_support_files() -> None:
    if not SUPPORT_DIR.is_dir():
        raise FileNotFoundError(f"Dossier support absent : {SUPPORT_DIR}")

    for source in sorted(SUPPORT_DIR.iterdir()):
        if source.is_file():
            destination = ROOT / source.name
            shutil.copy2(source, destination)
            print(f"OK  support/{source.name} -> {destination.name}")

    documentation_dir = ROOT / "DOCUMENTATION"
    documentation_dir.mkdir(exist_ok=True)
    for name in ("SCHEMA_SQLITE_V2_12_3.sql", "README_PACK_V2_12_3_R10_PROPRE.md"):
        source = SUPPORT_DIR / name
        if source.exists():
            shutil.copy2(source, documentation_dir / name)

    audit_dir = ROOT / "AUDIT_R10"
    audit_dir.mkdir(exist_ok=True)
    for name in ("README.md", "PROMPT_CLAUDE_V2_12_3_R10.md", "COMPLETE.txt"):
        source = HERE / name
        if source.exists():
            shutil.copy2(source, audit_dir / name)


def create_reference_databases() -> None:
    helper = ROOT / "create_reference_databases.py"
    completed = subprocess.run([sys.executable, str(helper)], cwd=ROOT, text=True)
    if completed.returncode != 0:
        raise RuntimeError("Création des bases SQLite de référence impossible.")


def main() -> int:
    if shutil.which("patch") is None:
        print("ERREUR : la commande système 'patch' est requise.", file=sys.stderr)
        print("Sous Windows, exécuter ce script dans Git Bash.", file=sys.stderr)
        return 2
    for name, config in PATCHES.items():
        apply_one(name, config)
    install_support_files()
    create_reference_databases()
    print("R10_RECONSTRUCTION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
