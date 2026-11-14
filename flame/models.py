"""The data contract (docs/flame/design.md, section 6).

The JSON files keep camelCase keys (fuelPhase, o2Pct, pressureKPa); Python reads them as
snake_case. Dump with by_alias=True to get the JSON shape back.
Pressure is always kPa. A value like "10.2 psi" does not validate.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


def _ordered(r: tuple[float, float]) -> tuple[float, float]:
    if r[0] > r[1]:
        raise ValueError("range must be [min, max]")
    return r


Pct = Annotated[float, Field(ge=0, le=100)]
KPa = Annotated[float, Field(gt=0)]
PctRange = Annotated[tuple[Pct, Pct], AfterValidator(_ordered)]
KPaRange = Annotated[tuple[KPa, KPa], AfterValidator(_ordered)]
FlowRange = Annotated[tuple[float, float], AfterValidator(_ordered)]

Accession = Annotated[str, Field(pattern=r"^PSI-\d+$")]
FuelPhase = Literal["solid", "liquid", "gas", "aerosol", "none"]
Topic = Literal["prevention", "detection", "suppression", "fundamental"]


class Model(BaseModel):
    # extra="forbid": a misspelt key in a data file is an error, not a silently missing value
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class Publication(Model):
    title: str
    authors: str | None = None
    doi: str | None = None
    url: str | None = None


class Investigation(Model):
    accession: Accession
    acronym: str
    title: str
    kind: Literal["flight", "ground"]          # from PSI "Project Type"
    sub_area: str                              # PSI "SubResearch Area"
    fuel_phase: FuelPhase
    hardware: list[str]                        # short names: CIR, MDCA, MSG, SPICE duct, ACME
    topics: list[Topic]
    objectives: str
    approach: str
    hypothesis: str
    earth_benefits: str
    related: list[Accession]
    publications: list[Publication]
    psi_url: str
    doi: str | None = None
    summary: str                               # 2-3 sentences, written by the LLM, read by a person


class Provenance(Model):
    source: str
    quote: str


class Envelope(Model):
    """One family of test conditions. An investigation can have several."""
    accession: Accession
    label: str
    fuel: str
    geometry: str
    o2_pct: PctRange | None
    pressure_kpa: KPaRange | None = Field(alias="pressureKPa")
    flow_mps: FlowRange | None
    gravity: Literal["micro", "earth", "partial-proxy"]
    diluent: str | None = None
    measured: list[str]
    sensors: list[str]
    key_finding: str
    provenance: list[Provenance]               # where each number came from
    verified: bool                             # a teammate checked it against the source


class Marker(Model):
    planet: Literal["moon", "mars"]
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=360)
    altitude_km: float | None = None           # set for things in orbit


class Habitat(Model):
    id: str
    name: str
    body: Literal["moon", "mars", "orbit", "earth"]
    o2_pct: PctRange
    pressure_kpa: KPaRange = Field(alias="pressureKPa")
    gravity: Literal["micro", "lunar", "martian", "earth"]
    gravity_g: float = Field(ge=0)
    assumed: bool                              # true until a NASA source is on record
    source_url: str
    notes: str
    marker: Marker | None = None


class Incident(Model):
    id: str
    name: str
    year: int
    o2_pct: Pct | None
    pressure_kpa: KPa | None = Field(alias="pressureKPa")
    cabin_fire: bool                           # false = shown in the list, kept off the gap map
    lesson: str
    source_url: str


class Insight(Model):
    habitat_id: str
    text: str
    cited: list[str]


class MaterialLimit(Model):
    """A measured flammability limit of one material at one gravity level (calculator input).

    uloi = oxygen at which the material burns about half the time; moc = maximum oxygen at which
    it consistently self-extinguishes; extinction = oxygen at which an observed flame went out.
    Reduced-gravity rows come from short drop-tower or sounding-rocket tests (see method).
    """
    material_id: str
    material: str
    form: Literal["film", "fabric", "sheet", "rod"]
    thickness_mm: float | None = Field(default=None, gt=0)
    gravity: Literal["micro", "lunar", "martian", "earth"]
    gravity_g: float = Field(ge=0)
    pressure_kpa: KPa = Field(alias="pressureKPa")
    flow_mps: float | None = None              # forced flow; None = buoyant flow only
    uloi_pct: Pct | None = None
    moc_pct: Pct | None = None
    extinction_pct: Pct | None = None
    method: str
    in_psi: bool                               # False = NASA test outside the PSI database
    provenance: list[Provenance]
    verified: bool


class DemoAnswer(Model):
    question: str
    answer: str
    charts: list[dict]                         # chart specs, checked by flame.assistant.charts
    cited: list[str]

class PsiTest(Model):
    """One row of a PSI experiment table after cleaning (flame/ingest/clean_tables.py).

    kind: "test" = one run; "test_day" = one ISS session summarised in one row (e.g. ACME BRE);
    "matrix" = the planned range of conditions, not individual runs (FLEX-2).
    Ranges are [min, max]; a single measured value is stored as [x, x]. None = the table does
    not give it. Every row points back to its file and row number in the raw layer.
    """
    accession: Accession
    experiment: str
    table: str                                 # file in blackfox/db/knowledge/raw_data/psi_combustion/tables
    source_row: int = Field(ge=1)              # 1 = first data row under the header
    test_id: str
    kind: Literal["test", "test_day", "matrix"]
    config: str | None = None                  # concurrent / opposed, normal / inverse
    fuel: str
    fuel_phase: FuelPhase
    gravity: Literal["micro", "earth"]
    o2_pct: PctRange | None = None
    pressure_kpa: KPaRange | None = Field(default=None, alias="pressureKPa")
    flow_mps: FlowRange | None = None
    diluent: str | None = None
    ignited: bool | None = None
    outcome: str | None = None                 # extinction, self_extinguished, flow_terminated, ...
    burn_time_s: float | None = Field(default=None, ge=0)
    spread_rate_mm_s: float | None = Field(default=None, ge=0)
    notes: str = ""
