#!/usr/bin/env python3
"""Tests hors matériel V2.12.3 : logique fermée EA, limites de rampe, plausibilité et SQLite."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton

import main_ihm_relais_rp2040_v2_12_3 as appmod


class FakeSerial:
    def __init__(self, responses: dict[str, object]):
        self.responses = dict(responses)
        self.last_command = ""
        self.is_open = True
        self.commands: list[str] = []

    def reset_input_buffer(self) -> None:
        pass

    def write(self, payload: bytes) -> int:
        self.last_command = payload.decode("ascii").strip()
        self.commands.append(self.last_command)
        if self.last_command == "FUNC:GEN:SEL NONE":
            self.responses["FUNC:GEN:SEL?"] = "NONE"
        return len(payload)

    def flush(self) -> None:
        pass

    def readline(self) -> bytes:
        value = self.responses.get(self.last_command, "")
        if isinstance(value, list):
            current = value.pop(0) if value else ""
        else:
            current = value
        return (str(current) + "\n").encode("ascii")

    def close(self) -> None:
        self.is_open = False


def make_ea(responses: dict[str, str]) -> appmod.EAPSU:
    ea = appmod.EAPSU()
    ea.ser = FakeSerial(responses)
    ea.connected = True
    return ea


def test_scpi_closed_logic() -> None:
    # Cas qui bloquait la R1 : générateur déjà sur NONE.
    good_none = make_ea({
        "FUNC:GEN:SEL?": "NONE",
        "OUTP?": "0",
        "MEAS:VOLT?": "0.015",
        "SYST:ERR?": '+0,"No error"',
    })
    result = good_none.safe_stop_and_confirm(settle_s=0, attempts=1)
    assert result["confirmed"] is True, result
    assert "FUNC:GEN:WAVE:STAT STOP" not in good_none.ser.commands
    assert "FUNC:GEN:WAVE:STAT?" not in good_none.ser.commands
    assert "OUTP OFF" in good_none.ser.commands
    assert "VOLT 0" in good_none.ser.commands
    assert "FUNC:GEN:SEL NONE" in good_none.ser.commands

    # Cas générateur arbitraire actif : STOP est envoyé puis le mode est quitté.
    good_active = make_ea({
        "FUNC:GEN:SEL?": "VOLTAGE",
        "OUTP?": "OFF",
        "MEAS:VOLT?": "0.010",
        "SYST:ERR?": '+0,"No error"',
    })
    result = good_active.safe_stop_and_confirm(settle_s=0, attempts=1)
    assert result["confirmed"] is True, result
    assert "FUNC:GEN:WAVE:STAT STOP" in good_active.ser.commands

    empty_error = make_ea({
        "FUNC:GEN:SEL?": "NONE",
        "OUTP?": "0",
        "MEAS:VOLT?": "0.015",
        "SYST:ERR?": "",
    })
    result = empty_error.safe_stop_and_confirm(settle_s=0, attempts=1, confirm_timeout_s=0.05, poll_interval_s=0.01)
    assert result["confirmed"] is False
    assert any("SCPI" in err for err in result["errors"])

    empty_selection = make_ea({
        "FUNC:GEN:SEL?": "",
        "OUTP?": "0",
        "MEAS:VOLT?": "0.015",
        "SYST:ERR?": '+0,"No error"',
    })
    result = empty_selection.safe_stop_and_confirm(settle_s=0, attempts=1, confirm_timeout_s=0.05, poll_interval_s=0.01)
    assert result["confirmed"] is False
    assert any("sélection générateur" in err for err in result["errors"])

    too_high = make_ea({
        "FUNC:GEN:SEL?": "NONE",
        "OUTP?": "0",
        "MEAS:VOLT?": "0.500",
        "SYST:ERR?": '+0,"No error"',
    })
    result = too_high.safe_stop_and_confirm(settle_s=0, attempts=1, confirm_timeout_s=0.05, poll_interval_s=0.01)
    assert result["confirmed"] is False
    assert any("tension résiduelle" in err for err in result["errors"])

    output_on = make_ea({
        "FUNC:GEN:SEL?": "NONE",
        "OUTP?": "ON",
        "MEAS:VOLT?": "0.015",
        "SYST:ERR?": '+0,"No error"',
    })
    result = output_on.safe_stop_and_confirm(settle_s=0, attempts=1, confirm_timeout_s=0.05, poll_interval_s=0.01)
    assert result["confirmed"] is False
    assert any("sortie non coupée" in err for err in result["errors"])

    # R3 : une sortie peu chargée peut rester >0,200 V pendant plusieurs lectures.
    delayed_discharge = make_ea({
        "FUNC:GEN:SEL?": "NONE",
        "OUTP?": "OFF",
        "MEAS:VOLT?": ["1.200", "0.650", "0.280", "0.120"],
        "SYST:ERR?": '+0,"No error"',
    })
    result = delayed_discharge.safe_stop_and_confirm(
        settle_s=0, attempts=1, confirm_timeout_s=0.20, poll_interval_s=0.001
    )
    assert result["confirmed"] is True, result
    assert result["poll_count"] >= 4, result
    assert result["measured_voltage_v"] <= 0.200

    # En cas d'échec persistant, le diagnostic conserve la dernière tension et la durée.
    persistent_voltage = make_ea({
        "FUNC:GEN:SEL?": "NONE",
        "OUTP?": "OFF",
        "MEAS:VOLT?": "0.450",
        "SYST:ERR?": '+0,"No error"',
    })
    result = persistent_voltage.safe_stop_and_confirm(
        settle_s=0, attempts=1, confirm_timeout_s=0.05, poll_interval_s=0.01
    )
    assert result["confirmed"] is False
    assert result["poll_count"] >= 2
    assert result["confirmation_elapsed_s"] >= 0.04
    assert any("après 0.1 s" in err or "tension résiduelle" in err for err in result["errors"]), result

    # Une ancienne erreur est purgée et tracée, puis le contrôle courant peut réussir.
    stale_error = make_ea({
        "FUNC:GEN:SEL?": "NONE",
        "OUTP?": "0",
        "MEAS:VOLT?": "0.015",
        "SYST:ERR?": ['-221,"Settings conflict"', '+0,"No error"', '+0,"No error"'],
    })
    result = stale_error.safe_stop_and_confirm(settle_s=0, attempts=1)
    assert result["confirmed"] is True, result
    assert result["preexisting_scpi_errors"] == ['-221,"Settings conflict"']

    assert appmod.EAPSU.generator_selection_is_none("NONE")
    assert appmod.EAPSU.generator_selection_is_arbitrary("VOLTAGE")
    assert appmod.EAPSU.generator_selection_is_arbitrary("CURR")
    assert appmod.EAPSU.generator_state_is_running("RUN")
    assert appmod.EAPSU.generator_state_is_stopped("STOPPED")


def test_ui_limits_and_plausibility(ihm: appmod.IhmRelaisRp2040) -> None:
    ihm.doubleSpinBox_voltage_vmax.setValue(30.0)
    max_30 = ihm.voltage_update_ramp_limits()
    assert max_30 <= (30.0 / 0.145) and (30.0 / 0.145) - max_30 < 0.0011
    assert abs(ihm.doubleSpinBox_voltage_ramp_up_s.maximum() - max_30) < 0.002

    ihm.doubleSpinBox_voltage_vmax.setValue(20.0)
    max_20 = ihm.voltage_update_ramp_limits()
    assert max_20 <= (20.0 / 0.145) and (20.0 / 0.145) - max_20 < 0.0011

    ihm.voltage_ramp_info = {
        "mode": "PICKUP",
        "start_v": 0.0,
        "end_v": 20.0,
        "duration_s": 20.0,
    }
    ihm.voltage_results["PICKUP"] = {"GLOBAL": 12.0}
    ihm.voltage_time_results["PICKUP"] = {"GLOBAL": 12_300_000}
    plausible = ihm.voltage_evaluate_plausibility("PICKUP")
    assert plausible["status"] == "OK", plausible

    ihm.voltage_time_results["PICKUP"] = {"GLOBAL": 19_800_000}
    incoherent = ihm.voltage_evaluate_plausibility("PICKUP")
    assert incoherent["status"] == "INCOHERENT", incoherent

    ihm.voltage_results["PICKUP"] = {"GLOBAL": 19.8}
    ihm.voltage_time_results["PICKUP"] = {"GLOBAL": 12_000_000}
    incoherent = ihm.voltage_evaluate_plausibility("PICKUP")
    assert incoherent["status"] == "INCOHERENT", incoherent




def test_test_state_reset(ihm: appmod.IhmRelaisRp2040) -> None:
    """Un verdict de l'essai précédent ne doit jamais contaminer le suivant."""
    ihm.voltage_plausibility = {"PICKUP": {"status": "INCOHERENT"}, "DROPOUT": {}}
    ihm.voltage_result_override = "ARRET_EA_NON_CONFIRME"
    ihm.voltage_ea_stop_confirmation = {"confirmed": False, "errors": ["ancien essai"]}
    ihm.voltage_last_stop_diagnostic = "ancien diagnostic"

    ihm.voltage_reset_assessment_state()

    assert ihm.voltage_plausibility == {"PICKUP": {}, "DROPOUT": {}}
    assert ihm.voltage_result_override == ""
    assert ihm.voltage_ea_stop_confirmation.get("confirmed") is None
    assert ihm.voltage_last_stop_diagnostic == ""

def test_modal_test_fini(ihm: appmod.IhmRelaisRp2040) -> None:
    ihm.auto_end_validation_pending = True
    ihm.last_finished_sn = "TEST"
    called: list[bool] = []
    original = ihm.auto_validate_end_of_test
    ihm.auto_validate_end_of_test = lambda: called.append(True)

    def close_modal() -> None:
        dialog = QApplication.activeModalWidget()
        assert dialog is not None
        buttons = dialog.findChildren(QPushButton)
        assert any(button.text() == "TEST FINI" and button.isVisible() for button in buttons)
        dialog.accept()

    QTimer.singleShot(30, close_modal)
    try:
        ihm.show_auto_finish_validation_dialog(True)
    finally:
        ihm.auto_validate_end_of_test = original
        ihm.auto_end_validation_pending = False
    assert called

def test_sqlite_save(ihm: appmod.IhmRelaisRp2040, base: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "chronometrie_contacts.sqlite3"
        shutil.copy2(base / "chronometrie_contacts_REFERENCE_VIDE.sqlite3", db)
        # Émule une base V2.12.2 : les 40 colonnes historiques sont conservées,
        # les 12 colonnes V2.12.3 sont retirées avant d'exécuter la migration.
        with closing(sqlite3.connect(db)) as con:
            all_columns = [
                row[1] for row in con.execute(
                    "PRAGMA table_info(mesures_tension_fonctionnement)"
                )
            ]
            legacy_columns = all_columns[:40]
            quoted = ", ".join(f'"{name}"' for name in legacy_columns)
            con.execute(
                f"CREATE TABLE mesures_tension_v2122 AS "
                f"SELECT {quoted} FROM mesures_tension_fonctionnement WHERE 0"
            )
            con.execute("DROP TABLE mesures_tension_fonctionnement")
            con.execute(
                "ALTER TABLE mesures_tension_v2122 "
                "RENAME TO mesures_tension_fonctionnement"
            )

        ihm.chrono_db_file = db
        ihm.voltage_init_db()
        ihm.voltage_init_db()  # idempotence

        expected_columns = {
            "pickup_plausibility_status",
            "dropout_plausibility_status",
            "plausibility_json",
            "ea_stop_confirmed",
            "ea_final_output_state",
            "ea_final_voltage_v",
            "ea_final_generator_state",
            "ea_stop_detail",
        }
        with closing(sqlite3.connect(db)) as con:
            columns = {row[1] for row in con.execute("PRAGMA table_info(mesures_tension_fonctionnement)")}
        assert expected_columns <= columns

        ihm.lineEdit_voltage_lot.setText("LOT_TEST")
        ihm.lineEdit_voltage_relais.setText("RELAIS_TEST")
        ihm.lineEdit_voltage_sn.setText("001")
        ihm.lineEdit_voltage_date.setText("15/07/2026")
        ihm.lineEdit_voltage_ambiance.setText("20")
        ihm.lineEdit_voltage_test.setText("TEST V2.12.3")
        ihm.active_voltage_calibration = {
            "id": 1,
            "calibration_date": "15/07/2026",
            "divider_ratio": 12.818182,
            "offset_mv": 0,
            "check_error_v": 0.005,
        }
        ihm.voltage_capture_policy = "FIRST_PASSAGE"
        ihm.voltage_results = {"PICKUP": {"GLOBAL": 12.0}, "DROPOUT": {}}
        ihm.voltage_raw_results = {"PICKUP": {"GLOBAL": 7490}, "DROPOUT": {}}
        ihm.voltage_time_results = {"PICKUP": {"GLOBAL": 12_300_000}, "DROPOUT": {}}
        ihm.voltage_effective_ramp_s = {"PICKUP": 20.5, "DROPOUT": None}
        ihm.voltage_plausibility = {
            "PICKUP": {
                "status": "OK",
                "expected_elapsed_s": 12.0,
                "elapsed_error_s": 0.3,
            },
            "DROPOUT": {},
        }
        ihm.voltage_ea_stop_confirmation = {
            "confirmed": True,
            "output_state": "0",
            "measured_voltage_v": 0.012,
            "generator_state": "STOP",
            "errors": [],
        }
        ihm.voltage_result_override = ""
        ihm.voltage_save_result()

        with closing(sqlite3.connect(db)) as con:
            con.row_factory = sqlite3.Row
            row = con.execute(
                "SELECT * FROM mesures_tension_fonctionnement ORDER BY id DESC LIMIT 1"
            ).fetchone()
        assert row is not None
        assert row["pickup_plausibility_status"] == "OK"
        assert row["ea_stop_confirmed"] == 1
        assert abs(row["ea_final_voltage_v"] - 0.012) < 1e-9
        assert row["resultat"] == "OK"



def test_pdf_export_all_columns(ihm: appmod.IhmRelaisRp2040) -> None:
    headers = [
        ("lot", "Lot"), ("relais", "Relais"), ("sn", "SN"),
        ("relay_type", "Type"), ("nb_inverseurs", "Inv."),
        ("pickup_global_v", "Collage / BE V"),
        ("dropout_global_v", "Décollage / BR V"),
        ("calibration_id", "Cal."),
        ("pickup_plausibility_status", "Plaus. BE"),
        ("dropout_plausibility_status", "Plaus. retour"),
        ("ea_stop_confirmed", "Arrêt EA"),
        ("ea_final_voltage_v", "V finale EA"),
        ("calibration_error_v", "Err. cal. V"),
        ("resultat", "Résultat"),
    ]
    row = {key: "X" for key, _label in headers}
    row.update({"lot": "LOT_PDF", "ea_final_voltage_v": 0.01, "resultat": "OK"})
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "export_14_colonnes.pdf"
        ihm.write_table_pdf(str(pdf), "TEST 14 COLONNES", headers, [row])
        assert pdf.exists() and pdf.stat().st_size > 1000


def test_static_markers(base: Path) -> None:
    py_text = (base / "main_ihm_relais_rp2040_v2_12_3.py").read_text(encoding="utf-8")
    ui_text = (base / "ihm_relais_rp2040_28vdc_precision_v2_12_3.ui").read_text(encoding="utf-8")
    assert "pushButton_prod_reload_base" in ui_text
    assert "pushButton_auto_fin_essai" not in py_text
    assert "ARRÊT EA NON CONFIRMÉ" in py_text
    assert "generator_selection_is_none" in py_text
    assert "EA_STOP_CONFIRM_TIMEOUT_S = 5.000" in py_text
    assert "voltage_last_stop_diagnostic" in py_text
    assert "ne pas envoyer WAVE:STAT STOP hors mode générateur" in py_text
    assert "FUNC:GEN:SEL?" in py_text
    assert "voltage_ea_monitor_timer" in py_text
    assert "voltage_reset_assessment_state" in py_text
    assert "QPageLayout.Landscape" in py_text
    assert "pickup_plausibility_status" in py_text


def main() -> None:
    base = Path(__file__).resolve().parent
    test_scpi_closed_logic()
    QApplication.instance() or QApplication([])
    ihm = appmod.IhmRelaisRp2040()
    try:
        test_ui_limits_and_plausibility(ihm)
        test_test_state_reset(ihm)
        test_modal_test_fini(ihm)
        test_sqlite_save(ihm, base)
        test_pdf_export_all_columns(ihm)
        test_static_markers(base)
    finally:
        ihm.close()
    print("V2_12_3_SAFETY_PLAUSIBILITY_TESTS_OK")


if __name__ == "__main__":
    main()
