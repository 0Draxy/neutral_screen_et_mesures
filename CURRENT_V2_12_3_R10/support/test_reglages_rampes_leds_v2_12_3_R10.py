from __future__ import annotations

import ast
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parent
PY_FILE = BASE / "main_ihm_relais_rp2040_v2_12_3.py"
UI_FILE = BASE / "ihm_relais_rp2040_28vdc_precision_v2_12_3.ui"


def load_harness_class():
    source = PY_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "IhmRelaisRp2040")
    wanted = {
        "voltage_refresh_contact_leds",
        "voltage_set_contact_indicator",
        "voltage_measure_settings_snapshot",
        "voltage_load_measure_settings",
        "voltage_save_measure_settings",
        "voltage_commit_measure_settings",
        "voltage_capture_run_settings",
        "voltage_run_setting",
    }
    methods = [node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert {node.name for node in methods} == wanted
    module = ast.parse("class Harness:\n    pass\n")
    harness = module.body[0]
    harness.body = methods
    ast.fix_missing_locations(module)
    namespace = {
        "Path": Path,
        "json": json,
        "os": os,
        "Qt": SimpleNamespace(AlignCenter=0),
    }
    exec(compile(module, str(PY_FILE), "exec"), namespace)
    return namespace["Harness"]


class FakeSpin:
    def __init__(self, value):
        self._value = float(value)
        self.blocked = False
        self.interpret_count = 0

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = float(value)

    def interpretText(self):
        self.interpret_count += 1

    def blockSignals(self, blocked):
        self.blocked = bool(blocked)


class FakeIntSpin(FakeSpin):
    def value(self):
        return int(self._value)


class FakeLabel:
    def __init__(self):
        self.size = None
        self.alignment = None
        self.text = None
        self.tooltip = None
        self.style = None

    def setFixedSize(self, width, height):
        self.size = (width, height)

    def setAlignment(self, alignment):
        self.alignment = alignment

    def setText(self, text):
        self.text = text

    def setToolTip(self, text):
        self.tooltip = text

    def setStyleSheet(self, text):
        self.style = text


def make_settings_harness(tmp_path: Path):
    Harness = load_harness_class()
    obj = Harness()
    obj.doubleSpinBox_voltage_vmax = FakeSpin(30.0)
    obj.doubleSpinBox_voltage_ramp_up_s = FakeSpin(3.0)
    obj.doubleSpinBox_voltage_ramp_down_s = FakeSpin(4.0)
    obj.doubleSpinBox_voltage_current_limit = FakeSpin(0.2)
    obj.doubleSpinBox_voltage_chrono_v = FakeSpin(28.0)
    obj.doubleSpinBox_voltage_interphase_s = FakeSpin(6.0)
    obj.voltage_measure_settings_file = tmp_path / "voltage_measure_settings.json"
    obj._voltage_loading_measure_settings = False
    obj.voltage_run_settings = {}
    obj.voltage_update_ramp_limits = lambda: None
    return obj


def test_true_round_indicators():
    Harness = load_harness_class()
    label = FakeLabel()
    Harness.voltage_set_contact_indicator(label, "R1", "1", "green")
    assert label.size == (18, 18)
    assert label.text == ""
    assert "background-color" in label.style
    assert "border-radius: 9px" in label.style
    assert "0,205,75" in label.style
    assert "fermé" in label.tooltip

    Harness.voltage_set_contact_indicator(label, "T1", "0", "red")
    assert label.text == ""
    assert "90,25,25" in label.style
    assert "ouvert" in label.tooltip

    Harness.voltage_set_contact_indicator(label, "R4", None, "green", selected=False)
    assert "165,165,165" in label.style
    assert "non sélectionné" in label.tooltip


def test_voltage_led_filter():
    Harness = load_harness_class()
    obj = Harness()
    obj.spinBox_voltage_nb_inverseurs = FakeIntSpin(2)
    obj.contacts_known_values = ["1", "0", "1", "1", "0", "1", "0", "0"]
    for name in ("r1", "r2", "r3", "r4", "t1", "t2", "t3", "t4"):
        setattr(obj, f"label_voltage_led_{name}", FakeLabel())
    obj.voltage_refresh_contact_leds()
    assert obj.label_voltage_led_r1.text == ""
    assert "0,205,75" in obj.label_voltage_led_r1.style
    assert "90,25,25" in obj.label_voltage_led_t1.style
    assert "non sélectionné" in obj.label_voltage_led_r3.tooltip


def test_interphase_persistence_and_freeze():
    with tempfile.TemporaryDirectory() as tmp:
        obj = make_settings_harness(Path(tmp))
        obj.voltage_save_measure_settings()
        saved = json.loads(obj.voltage_measure_settings_file.read_text(encoding="utf-8"))
        assert saved["interphase_s"] == 6.0
        assert saved["chrono_supply_v"] == 28.0

        obj.doubleSpinBox_voltage_interphase_s.setValue(9.5)
        obj.voltage_save_measure_settings()
        obj.doubleSpinBox_voltage_interphase_s.setValue(3.0)
        obj.voltage_load_measure_settings()
        assert obj.doubleSpinBox_voltage_interphase_s.value() == 9.5

        run = obj.voltage_capture_run_settings()
        assert run["ramp_up_s"] == 3.0
        assert run["ramp_down_s"] == 4.0
        assert run["interphase_s"] == 9.5
        assert run["chrono_supply_v"] == 28.0
        obj.doubleSpinBox_voltage_interphase_s.setValue(12.0)
        assert obj.voltage_run_setting("interphase_s", obj.doubleSpinBox_voltage_interphase_s) == 9.5


def method_source(name: str) -> str:
    source = PY_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "IhmRelaisRp2040")
    method = next(node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name)
    lines = source.splitlines()
    return "\n".join(lines[method.lineno - 1:method.end_lineno])


def test_ramp_mapping():
    pickup = method_source("voltage_begin_pickup")
    dropout = method_source("voltage_begin_dropout")
    complete = method_source("voltage_handle_scan_complete")
    assert 'voltage_run_setting("ramp_up_s"' in pickup
    assert dropout.count('voltage_run_setting("ramp_down_s"') == 2
    assert 'self.voltage_set_coil_hold("BR")' in dropout
    assert 'self.voltage_set_coil_hold("BE")' in dropout
    assert 'voltage_run_setting("interphase_s"' in complete


def test_ui():
    root = ET.parse(UI_FILE).getroot()
    title = root.find('.//widget[@class="QMainWindow"]/property[@name="windowTitle"]/string')
    assert title is not None and "R10" in (title.text or "")
    group_box = root.find('.//widget[@name="groupBox_voltage_contacts"]')
    assert group_box is not None
    for side in ("r", "t"):
        for index in range(1, 5):
            widget = root.find(f'.//widget[@name="label_voltage_led_{side}{index}"]')
            assert widget is not None
            rect = widget.find('./property[@name="geometry"]/rect')
            assert rect.findtext("width") == "18"
            assert rect.findtext("height") == "18"
            style = widget.findtext('./property[@name="styleSheet"]/string') or ""
            assert "border-radius: 9px" in style
            assert (widget.findtext('./property[@name="text"]/string') or "") == ""


def main():
    test_true_round_indicators()
    test_voltage_led_filter()
    test_interphase_persistence_and_freeze()
    test_ramp_mapping()
    test_ui()
    print("REGLAGES_RAMPES_LEDS_R10_TESTS_OK")


if __name__ == "__main__":
    main()
