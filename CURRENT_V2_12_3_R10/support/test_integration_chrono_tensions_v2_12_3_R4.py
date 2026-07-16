from __future__ import annotations

import ast
import shutil
import sqlite3
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
MAIN = BASE / "main_ihm_relais_rp2040_v2_12_3.py"
DB = BASE / "chronometrie_contacts_REFERENCE_VIDE.sqlite3"


def check_source() -> None:
    source = MAIN.read_text(encoding="utf-8")
    ast.parse(source)
    required = [
        "def chrono_export_voltage_rows",
        "def chrono_database_combined_rows",
        "Chronométrie contacts et tensions",
        "mesures_tension_fonctionnement",
        "chronometrie_et_tensions_lot_",
        "Tension collage / BE globale (V)",
        "Tension décollage / BR globale (V)",
    ]
    missing = [token for token in required if token not in source]
    if missing:
        raise AssertionError(f"Éléments R4 absents : {missing}")


def check_database() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "chronometrie_contacts.sqlite3"
        shutil.copy2(DB, db)
        con = sqlite3.connect(db)
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            assert "mesures_chrono_contacts" in tables
            assert "mesures_tension_fonctionnement" in tables
            con.execute(
                """
                INSERT INTO mesures_chrono_contacts(
                    lot,date_test,relais,ambiance_c,nom_test,sn,relay_type,action,
                    nb_inverseurs,capture_ms,pulse_ms,limite_temps_ms,limite_rebond_ms,
                    resultat,overflow,details_json,events_json,timestamp
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                ("LOT-R4","16/07/2026","REL-1","20","Essai","001","BISTABLE","BE",
                 2,50,10,1.5,2.0,"OK",0,'{"lignes_action":[]}','{}','2026-07-16 10:00:00'),
            )
            con.execute(
                """
                INSERT INTO mesures_tension_fonctionnement(
                    lot,date_test,relais,ambiance_c,nom_test,sn,relay_type,nb_inverseurs,
                    pickup_global_v,dropout_global_v,pickup_json,dropout_json,
                    pickup_plausibility_status,dropout_plausibility_status,
                    ea_stop_confirmed,ea_final_voltage_v,resultat,timestamp
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                ("LOT-R4","16/07/2026","REL-1","20","Essai","001","BISTABLE",2,
                 12.345,4.567,'{"1":12.340,"2":12.350}','{"1":4.560,"2":4.570}',
                 "OK","OK",1,0.012,"OK",'2026-07-16 10:05:00'),
            )
            con.commit()
            row = con.execute(
                """
                WITH toutes AS (
                    SELECT 'CHRONO' source, lot, sn FROM mesures_chrono_contacts
                    UNION ALL
                    SELECT 'TENSION' source, lot, sn FROM mesures_tension_fonctionnement
                )
                SELECT SUM(source='CHRONO'), SUM(source='TENSION'), COUNT(DISTINCT sn)
                FROM toutes WHERE lot='LOT-R4'
                """
            ).fetchone()
            assert row == (1, 1, 1), row
        finally:
            con.close()


def main() -> None:
    check_source()
    check_database()
    print("INTEGRATION_CHRONO_TENSIONS_R4_OK")


if __name__ == "__main__":
    main()
