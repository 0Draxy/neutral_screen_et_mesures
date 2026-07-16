from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRODUCTION_DB = ROOT / "production_essais_REFERENCE_VIDE.sqlite3"
CHRONO_DB = ROOT / "chronometrie_contacts_REFERENCE_VIDE.sqlite3"

PRODUCTION_SQL = r"""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS essais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot TEXT NOT NULL DEFAULT '',
    sn TEXT NOT NULL DEFAULT '',
    designation TEXT NOT NULL DEFAULT '',
    nb_inverseurs INTEGER NOT NULL DEFAULT 2,
    operateur TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL DEFAULT '',
    heure TEXT NOT NULL DEFAULT '',
    scenario TEXT NOT NULL DEFAULT '',
    resultat TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS operators (
    name TEXT PRIMARY KEY,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_essais_lot_sn ON essais(lot, sn);
CREATE INDEX IF NOT EXISTS idx_essais_lot_timestamp ON essais(lot, timestamp);
CREATE INDEX IF NOT EXISTS idx_essais_timestamp ON essais(timestamp);
"""

CHRONO_SQL = r"""
CREATE TABLE IF NOT EXISTS mesures_chrono_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot TEXT NOT NULL DEFAULT '',
    date_test TEXT NOT NULL DEFAULT '',
    relais TEXT NOT NULL DEFAULT '',
    ambiance_c TEXT NOT NULL DEFAULT '',
    nom_test TEXT NOT NULL DEFAULT '',
    sn TEXT NOT NULL DEFAULT '',
    relay_type TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL DEFAULT '',
    nb_inverseurs INTEGER NOT NULL DEFAULT 0,
    capture_ms INTEGER NOT NULL DEFAULT 0,
    pulse_ms INTEGER NOT NULL DEFAULT 0,
    limite_temps_ms REAL NOT NULL DEFAULT 0,
    limite_rebond_ms REAL NOT NULL DEFAULT 0,
    resultat TEXT NOT NULL DEFAULT '',
    overflow INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '',
    events_json TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_chrono_lot_sn ON mesures_chrono_contacts(lot, sn);
CREATE INDEX IF NOT EXISTS idx_chrono_timestamp ON mesures_chrono_contacts(timestamp);

CREATE TABLE IF NOT EXISTS calibrations_tension_ads1115 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calibration_date TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '',
    meter_reference TEXT NOT NULL DEFAULT '',
    valid_days INTEGER NOT NULL DEFAULT 365,
    low_actual_v REAL NOT NULL DEFAULT 0,
    low_raw INTEGER NOT NULL DEFAULT 0,
    high_actual_v REAL NOT NULL DEFAULT 0,
    high_raw INTEGER NOT NULL DEFAULT 0,
    check_actual_v REAL NOT NULL DEFAULT 0,
    check_raw INTEGER NOT NULL DEFAULT 0,
    divider_ratio REAL NOT NULL DEFAULT 0,
    offset_mv INTEGER NOT NULL DEFAULT 0,
    check_calculated_v REAL NOT NULL DEFAULT 0,
    check_error_v REAL NOT NULL DEFAULT 0,
    tolerance_v REAL NOT NULL DEFAULT 0.05,
    is_valid INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_calibration_active ON calibrations_tension_ads1115(is_active, is_valid);

CREATE TABLE IF NOT EXISTS mesures_tension_fonctionnement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot TEXT NOT NULL DEFAULT '',
    date_test TEXT NOT NULL DEFAULT '',
    relais TEXT NOT NULL DEFAULT '',
    ambiance_c TEXT NOT NULL DEFAULT '',
    nom_test TEXT NOT NULL DEFAULT '',
    sn TEXT NOT NULL DEFAULT '',
    relay_type TEXT NOT NULL DEFAULT 'MONOSTABLE',
    nb_inverseurs INTEGER NOT NULL DEFAULT 0,
    vmax_v REAL NOT NULL DEFAULT 0,
    ramp_up_s REAL NOT NULL DEFAULT 0,
    ramp_down_s REAL NOT NULL DEFAULT 0,
    interphase_s REAL NOT NULL DEFAULT 0,
    interphase_actual_s REAL,
    current_limit_a REAL NOT NULL DEFAULT 0,
    chrono_supply_v REAL NOT NULL DEFAULT 0,
    stable_ms INTEGER NOT NULL DEFAULT 0,
    capture_policy TEXT NOT NULL DEFAULT 'FIRST_PASSAGE',
    validation_policy TEXT NOT NULL DEFAULT 'STABLE_AFTER_CAPTURE',
    divider_ratio REAL NOT NULL DEFAULT 0,
    offset_mv INTEGER NOT NULL DEFAULT 0,
    calibration_id INTEGER,
    calibration_date TEXT NOT NULL DEFAULT '',
    calibration_error_v REAL,
    pickup_global_raw INTEGER,
    dropout_global_raw INTEGER,
    pickup_raw_json TEXT NOT NULL DEFAULT '{}',
    dropout_raw_json TEXT NOT NULL DEFAULT '{}',
    pickup_global_v REAL,
    dropout_global_v REAL,
    pickup_json TEXT NOT NULL DEFAULT '{}',
    dropout_json TEXT NOT NULL DEFAULT '{}',
    pickup_elapsed_s REAL,
    dropout_elapsed_s REAL,
    pickup_effective_ramp_s REAL,
    dropout_effective_ramp_s REAL,
    pickup_time_json TEXT NOT NULL DEFAULT '{}',
    dropout_time_json TEXT NOT NULL DEFAULT '{}',
    ea_readback_json TEXT NOT NULL DEFAULT '{}',
    pickup_plausibility_status TEXT NOT NULL DEFAULT '',
    dropout_plausibility_status TEXT NOT NULL DEFAULT '',
    pickup_expected_elapsed_s REAL,
    dropout_expected_elapsed_s REAL,
    pickup_elapsed_error_s REAL,
    dropout_elapsed_error_s REAL,
    plausibility_json TEXT NOT NULL DEFAULT '{}',
    ea_stop_confirmed INTEGER NOT NULL DEFAULT -1,
    ea_final_output_state TEXT NOT NULL DEFAULT '',
    ea_final_voltage_v REAL,
    ea_final_generator_state TEXT NOT NULL DEFAULT '',
    ea_stop_detail TEXT NOT NULL DEFAULT '',
    resultat TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_voltage_lot_sn ON mesures_tension_fonctionnement(lot, sn);
"""


def create_database(path: Path, script: str) -> None:
    if path.exists():
        return
    with sqlite3.connect(path) as connection:
        connection.executescript(script)
        connection.execute("PRAGMA user_version=2123")
        connection.commit()
    print(f"OK  {path.name}")


def main() -> int:
    create_database(PRODUCTION_DB, PRODUCTION_SQL)
    create_database(CHRONO_DB, CHRONO_SQL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
