"""Read access to flame/data/*.json.

Each file is read and validated once per process. A file that does not match
flame.models raises ValueError naming the file, which tests/flame catches before deploy.
Everything returned is a tuple: the rows are shared, so nobody gets to append to them.
"""

from functools import cache
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .models import DemoAnswer, Envelope, Habitat, Incident, Insight, Investigation, MaterialLimit

DATA = Path(__file__).parent / "data"
_MODELS = {"investigations": Investigation, "envelopes": Envelope, "habitats": Habitat,
           "incidents": Incident, "insights": Insight, "demo_answers": DemoAnswer,
           "material_limits": MaterialLimit}


@cache
def _load(name: str) -> tuple:
    try:
        return tuple(TypeAdapter(list[_MODELS[name]]).validate_json((DATA / f"{name}.json").read_bytes()))
    except ValidationError as e:
        raise ValueError(f"flame/data/{name}.json does not match the data contract:\n{e}") from e


def get_investigations() -> tuple[Investigation, ...]:
    return _load("investigations")


def get_investigation(accession: str) -> Investigation | None:
    return next((i for i in get_investigations() if i.accession == accession), None)


def get_envelopes(accession: str | None = None) -> tuple[Envelope, ...]:
    rows = _load("envelopes")
    return rows if accession is None else tuple(e for e in rows if e.accession == accession)


def get_habitats() -> tuple[Habitat, ...]:
    return _load("habitats")


def get_habitat(habitat_id: str) -> Habitat | None:
    return next((h for h in get_habitats() if h.id == habitat_id), None)


def get_incidents() -> tuple[Incident, ...]:
    return _load("incidents")


def get_insights(habitat_id: str) -> tuple[Insight, ...]:
    return tuple(i for i in _load("insights") if i.habitat_id == habitat_id)


def get_demo_answers() -> tuple[DemoAnswer, ...]:
    return _load("demo_answers")


def get_material_limits(material_id: str | None = None) -> tuple[MaterialLimit, ...]:
    rows = _load("material_limits")
    return rows if material_id is None else tuple(m for m in rows if m.material_id == material_id)
