"""Typed commands (handled instantly, no LLM):
  show                         full simulation snapshot
  select <part>                show that part's properties
  set <target>.<prop> = <val>  e.g. set hab.radius_m = 3   /   set environment.crew = 6
  add <type> <name>            e.g. add solar_array solar2
  remove <part>
  new [habitat|spacecraft]     start over from a default design
"""

import re

from . import simulator as sc
from .store import get_store, load_or_new

_SET = re.compile(r"^set\s+([\w-]+)\.(\w+)\s*(?:=|to|\s)\s*(.+)$", re.I)


def run_command(visitor_id: str, text: str) -> str | None:
    """A typed command -> snapshot text; None if the text is not a command (send it to the agent)."""
    t = text.strip()
    low = t.lower()
    word = low.split(maxsplit=1)[0] if low else ""
    if word not in ("show", "select", "set", "add", "remove", "new", "help"):
        return None
    if word == "help" and low == "help":
        return __doc__.split("Typed commands", 1)[1].split(":", 1)[1].strip("\n")
    store = get_store()
    try:
        if word == "new" and low in ("new", "new habitat", "new spacecraft"):
            d = sc.new_design(kind=low.split()[-1] if " " in low else "habitat")
        else:
            d = load_or_new(visitor_id)
            parts = t.split()
            if word == "show" and low == "show":
                pass
            elif word == "select" and len(parts) == 2:
                if parts[1] not in d["parts"]:
                    raise ValueError(f"no part named '{parts[1]}'; parts: {', '.join(d['parts'])}")
                d["selected"] = parts[1]
            elif word == "set" and (m := _SET.match(t)):
                sc.set_value(d, m.group(1), m.group(2), m.group(3).strip())
                if m.group(1) in d["parts"]:
                    d["selected"] = m.group(1)
            elif word == "add" and len(parts) == 3:
                sc.add_part(d, parts[2], parts[1])
            elif word == "remove" and len(parts) == 2:
                if parts[1] not in d["parts"]:
                    raise ValueError(f"no part named '{parts[1]}'")
                del d["parts"][parts[1]]
                if d["selected"] == parts[1]:
                    d["selected"] = next(iter(d["parts"]), "")
            else:
                return None      # looks like a sentence, not a command: let the agent handle it
    except ValueError as e:
        return f"error: {e}"
    store.put(visitor_id, d)
    return sc.report(d)
