#!/usr/bin/env python3
"""Tests hors matériel de la logique V2.12.3 de capture avant rebonds."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CaptureState:
    captured: bool = False
    capture_us: int = 0
    capture_mv: int = -1
    stable_start_us: int = 0
    done: bool = False
    result_us: int = 0
    result_mv: int = -1

    def update(self, now_us: int, expected: bool, mv: int, stable_us: int) -> None:
        if self.done:
            return
        if not expected:
            self.stable_start_us = 0
            return
        if not self.captured:
            self.captured = True
            self.capture_us = now_us
            self.capture_mv = mv
            self.stable_start_us = now_us
        elif self.stable_start_us == 0:
            self.stable_start_us = now_us
        if now_us - self.stable_start_us >= stable_us:
            self.done = True
            self.result_us = self.capture_us
            self.result_mv = self.capture_mv


def test_pickup_bounce() -> None:
    s = CaptureState()
    stable_us = 3000
    s.update(12_000_000, True, 12_000, stable_us)
    s.update(12_001_000, False, 12_001, stable_us)
    s.update(12_030_000, True, 12_030, stable_us)
    s.update(12_033_000, True, 12_033, stable_us)
    assert s.done
    assert s.result_mv == 12_000
    assert s.result_us == 12_000_000


def test_dropout_bounce() -> None:
    s = CaptureState()
    stable_us = 3000
    s.update(7_980_000, True, 12_020, stable_us)
    s.update(7_981_000, False, 12_019, stable_us)
    s.update(8_010_000, True, 11_990, stable_us)
    s.update(8_013_000, True, 11_987, stable_us)
    assert s.done
    assert s.result_mv == 12_020
    assert s.result_us == 7_980_000


def test_no_bounce() -> None:
    s = CaptureState()
    s.update(5_000_000, True, 10_500, 3000)
    s.update(5_003_000, True, 10_503, 3000)
    assert s.done
    assert s.result_mv == 10_500


def test_firmware_markers() -> None:
    base = Path(__file__).resolve().parent
    fw = (base / "rp2040_relais_28vdc_precision_v2_12_3_ADS1115_GP26_RGB.ino").read_text(encoding="utf-8")
    py = (base / "main_ihm_relais_rp2040_v2_12_3.py").read_text(encoding="utf-8")
    assert "voltageStableStartUs[5]" in fw
    assert "CAPTURE=FIRST_PASSAGE" in fw
    assert "VALIDATION=STABLE_AFTER_CAPTURE" in fw
    assert "Les rebonds ultérieurs ne remplacent jamais cette valeur" in fw
    assert "Téléverser le firmware V2.12.3" in py
    assert 'capture_policy != "FIRST_PASSAGE"' in py


def main() -> None:
    test_pickup_bounce()
    test_dropout_bounce()
    test_no_bounce()
    test_firmware_markers()
    print("CAPTURE_FIRST_PASSAGE_TESTS_OK")


if __name__ == "__main__":
    main()
