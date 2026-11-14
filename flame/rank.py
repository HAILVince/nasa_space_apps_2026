"""Which investigations matter most for one cabin atmosphere.

score = 0.45 condition + 0.25 topic + 0.20 fuel + 0.10 flight   (each part is 0..1)

condition  how close the nearest test envelope is to the habitat in oxygen and pressure.
           1 when they overlap; otherwise 1 minus a distance where the whole oxygen scale
           above air (79 points) and a factor of about 3.4 in pressure each count as "far".
           Scaled down when the gravity differs: PSI has no lunar or Martian tests at all.
topic      share of prevention / detection / suppression the investigation addresses.
fuel       solids rank first because cabins are full of them.
flight     a flight experiment outranks a ground study.

The weights are a judgement, not a measurement. They are returned with every row and the
dashboard lets the reader change them. `flame.calc.coverage` is the yes/no view of the
same question; this is the ordering.
"""

from math import log, sqrt
from typing import NamedTuple

from . import data
from .models import Envelope, Habitat, Investigation


class Weights(NamedTuple):
    condition: float
    topic: float
    fuel: float
    flight: float


DEFAULT_WEIGHTS = Weights(condition=0.45, topic=0.25, fuel=0.20, flight=0.10)
O2_SPAN = 79.0            # oxygen points between air and pure oxygen
LN_PRESSURE_SPAN = 1.23   # ln(101.3 / 29.6): sea-level cabin down to suit pressure
FUEL = {"solid": 1.0, "aerosol": 0.8, "liquid": 0.6, "gas": 0.5, "none": 0.3}
SAFETY_TOPICS = ("prevention", "detection", "suppression")


class RankedInvestigation(NamedTuple):
    accession: str
    acronym: str
    title: str
    score: float
    parts: dict[str, float]       # the four unweighted parts, so the page can show the breakdown
    no_condition_data: bool       # no envelope with both oxygen and pressure


def _gap(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance between two ranges; 0 when they overlap."""
    return max(0.0, a[0] - b[1], b[0] - a[1])


def gravity_factor(habitat_gravity: str, envelope_gravity: str) -> float:
    partial = ("lunar", "martian", "partial-proxy")
    a = "partial" if habitat_gravity in partial else habitat_gravity
    b = "partial" if envelope_gravity in partial else envelope_gravity
    if a == b:
        return 1.0
    return 0.85 if "partial" in (a, b) else 0.6     # 0 g against 1 g is the bigger jump


def condition_proximity(h: Habitat, envelopes: list[Envelope]) -> float:
    best = 0.0
    for env in envelopes:
        if env.o2_pct is None or env.pressure_kpa is None:
            continue
        d_o2 = _gap(h.o2_pct, env.o2_pct) / O2_SPAN
        d_p = _gap(tuple(map(log, h.pressure_kpa)), tuple(map(log, env.pressure_kpa))) / LN_PRESSURE_SPAN
        best = max(best, max(0.0, 1 - sqrt(d_o2 ** 2 + d_p ** 2)) * gravity_factor(h.gravity, env.gravity))
    return best


def rank_for_habitat(h: Habitat, investigations: list[Investigation] | None = None,
                     envelopes: list[Envelope] | None = None,
                     weights: Weights = DEFAULT_WEIGHTS) -> list[RankedInvestigation]:
    """Highest score first; ties by accession number. Weights are used as given, not renormalized."""
    investigations = data.get_investigations() if investigations is None else investigations
    envelopes = data.get_envelopes() if envelopes is None else envelopes
    rows = []
    for inv in investigations:
        own = [e for e in envelopes if e.accession == inv.accession]
        parts = {"condition": condition_proximity(h, own),
                 "topic": len(set(inv.topics) & set(SAFETY_TOPICS)) / len(SAFETY_TOPICS),
                 "fuel": FUEL[inv.fuel_phase],
                 "flight": 1.0 if inv.kind == "flight" else 0.5}
        score = sum(w * parts[name] for name, w in weights._asdict().items())
        usable = any(e.o2_pct is not None and e.pressure_kpa is not None for e in own)
        rows.append(RankedInvestigation(inv.accession, inv.acronym, inv.title, score, parts, not usable))
    rows.sort(key=lambda r: (-r.score, int(r.accession[4:])))
    return rows
