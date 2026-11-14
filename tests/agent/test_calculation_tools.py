import math

import pytest

from blackfox.tools.calc import calculate, calculate_batch, convert_units


def test_batch_keeps_results_and_errors_in_order():
    results = calculate_batch(["sqrt(16)", "1/0", "2*pi"])["results"]
    assert results[0]["result"] == 4
    assert "error" in results[1]
    assert results[2]["result"] == pytest.approx(2 * math.pi)
    assert "error" in calculate_batch(["1"] * 21)
    assert "error" in calculate("1e999")
    assert "error" in calculate("__import__('os')")


def test_unit_conversions_and_invalid_inputs():
    assert convert_units(1, "atm", "kPa")["result"] == pytest.approx(101.325)
    assert convert_units(32, "F", "C")["result"] == pytest.approx(0, abs=1e-12)
    assert convert_units(1, "kWh", "MJ")["result"] == pytest.approx(3.6)
    assert "error" in convert_units(1, "m", "kg")
    assert "error" in convert_units(1, "unknown", "m")
    assert "error" in convert_units(-1, "K", "C")
    assert "error" in convert_units(float("inf"), "m", "km")
