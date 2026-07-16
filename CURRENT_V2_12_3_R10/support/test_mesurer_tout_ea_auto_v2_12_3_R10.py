from __future__ import annotations

import ast
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parent
PY_FILE = BASE / "main_ihm_relais_rp2040_v2_12_3.py"
UI_FILE = BASE / "ihm_relais_rp2040_28vdc_precision_v2_12_3.ui"
INO_FILE = BASE / "rp2040_relais_28vdc_precision_v2_12_3_ADS1115_GP26_RGB.ino"
DB_FILE = BASE / "chronometrie_contacts_REFERENCE_VIDE.sqlite3"


def load_eapsu_class():
    source = PY_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "EAPSU")
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {
        "serial": SimpleNamespace(
            EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
            Serial=lambda *args, **kwargs: None,
        ),
        "re": re,
        "time": time,
        "EA_STATIC_CONFIRM_TIMEOUT_S": 3.0,
        "EA_STATIC_CONFIRM_POLL_INTERVAL_S": 0.15,
        "EA_STATIC_CONFIRM_MIN_TOL_V": 0.15,
        "EA_STATIC_CONFIRM_REL_TOL": 0.01,
        "EA_STOP_CONFIRM_MAX_V": 0.2,
        "EA_STOP_CONFIRM_SETTLE_S": 0.1,
        "EA_STOP_CONFIRM_ATTEMPTS": 2,
        "EA_STOP_CONFIRM_QUERY_TIMEOUT_S": 0.35,
        "EA_STOP_CONFIRM_TIMEOUT_S": 5.0,
        "EA_STOP_CONFIRM_POLL_INTERVAL_S": 0.15,
    }
    exec(compile(module, str(PY_FILE), "exec"), ns)
    return ns["EAPSU"]


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.timeout = 1.0


def make_fake_ea(base, measured=28.0):
    class FakeEA(base):
        def __init__(self):
            self.connected = True
            self.ser = FakeSerial()
            self.commands = []
            self.measured = measured
            self.last_scpi_error = ""

        def set_remote(self):
            self.commands.append("SYST:LOCK 1")

        def drain_scpi_errors(self, max_reads=8):
            return []

        def generator_selection(self):
            return "NONE"

        def send(self, command):
            self.commands.append(command)

        def output_state(self):
            return "ON"

        def measured_voltage(self):
            return self.measured

        def read_scpi_error(self):
            return '+0,"No error"'

    return FakeEA()


def test_static_ea_confirmation():
    EAPSU = load_eapsu_class()
    ea = make_fake_ea(EAPSU, 28.02)
    result = ea.configure_static_output_and_confirm(28.0, 0.2, timeout_s=0.05, poll_interval_s=0.01)
    assert result["confirmed"] is True, result
    assert "FUNC:GEN:SEL NONE" in ea.commands
    assert "VOLT 28.000000" in ea.commands
    assert "CURR 0.200000" in ea.commands
    assert "OUTP ON" in ea.commands

    bad = make_fake_ea(EAPSU, 26.0)
    result = bad.configure_static_output_and_confirm(28.0, 0.2, timeout_s=0.02, poll_interval_s=0.005)
    assert result["confirmed"] is False
    assert any("tension statique" in err for err in result["errors"])


def test_ui_python_firmware_contract():
    root = ET.parse(UI_FILE).getroot()
    title = root.find('.//widget[@class="QMainWindow"]/property[@name="windowTitle"]/string')
    assert title is not None and "R10" in (title.text or "")
    spin = root.find('.//widget[@name="doubleSpinBox_voltage_chrono_v"]')
    assert spin is not None
    assert spin.findtext('./property[@name="value"]/double') == "28.000000000000000"

    source = PY_FILE.read_text(encoding="utf-8")
    firmware = INO_FILE.read_text(encoding="utf-8")
    assert "METTRE LE SÉLECTEUR SUR EA" not in source
    assert "METTRE LE SÉLECTEUR SUR FIXE" not in source
    assert "EA_CHRONO_NO_GP26" in source
    assert 'source_suffix = ";EA"' in source
    assert "configure_static_output_and_confirm" in source
    assert "EA_CHRONO_NO_GP26" in firmware
    assert firmware.count("bool sourceEA") >= 3
    assert "if (sourceEA)" in firmware
    assert "if (!sourceEA) appliquerSelection32(false);" in firmware
    assert 'getToken(cmd, \';\', 5)' in firmware


def test_database_schema():
    con = sqlite3.connect(DB_FILE)
    try:
        cols = {row[1] for row in con.execute("PRAGMA table_info(mesures_tension_fonctionnement)")}
    finally:
        con.close()
    assert "chrono_supply_v" in cols

    source = PY_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "IhmRelaisRp2040")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "voltage_save_result")
    record_assign = next(
        n for n in ast.walk(method)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "record" for t in n.targets)
        and isinstance(n.value, ast.Dict)
    )
    keys = {k.value for k in record_assign.value.keys if isinstance(k, ast.Constant)}
    assert keys <= cols, sorted(keys - cols)


def main():
    test_static_ea_confirmation()
    test_ui_python_firmware_contract()
    test_database_schema()
    print("MESURER_TOUT_EA_AUTO_R10_TESTS_OK")


if __name__ == "__main__":
    main()
