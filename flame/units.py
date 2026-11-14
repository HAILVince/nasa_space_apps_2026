"""Unit helpers. Data is in kPa; psi exists only for display."""

KPA_PER_PSI = 6.89476


def kpa_to_psi(kpa: float) -> float:
    return kpa / KPA_PER_PSI


def psi_to_kpa(psi: float) -> float:
    return psi * KPA_PER_PSI


def o2_partial_kpa(o2_pct: float, pressure_kpa: float) -> float:
    return o2_pct / 100 * pressure_kpa


def mid(r: tuple[float, float]) -> float:
    return (r[0] + r[1]) / 2
