"""Tool registry. A tool is a plain, typed Python function decorated with
@tool(group=...). The MCP server publishes every tool of the enabled groups
(BLACKFOX_TOOL_GROUPS); argument schemas come from the type hints, descriptions
from the docstring.

Adding a tool = write a function in one of the modules in this package (or a new
module listed in TOOL_MODULES) - nothing else changes.

Context parameters (CONTEXT_PARAMS, e.g. visitor_id) are filled in by the harness,
never by the model: the harness removes them from the schema it shows the model and
injects the real value, so a model cannot read another visitor's memory.
"""

from dataclasses import dataclass
from typing import Callable

CONTEXT_PARAMS = ("visitor_id",)
TOOL_MODULES = ("design_tools", "research", "physics_tools", "memory_tools", "calc", "flame_tools", "scenario_tools", "ui_tools", "web_tools")


# What the model sees before it opens a category (the tools inside stay hidden until then).
CATEGORIES = {
    "design": "The user's current habitat/spacecraft design: read it, create a new one, change values, add/remove/select parts, list part types and materials.",
    "research": "Evidence: the NASA research text database and the Flame in Freefall (PSI) combustion investigations, material flammability limits and cited insights.",
    "physics": "Calculators: free fall, orbits, gravity, flames and combustion numbers, the cabin-fire simulation, the fire-lab scenario and the simulation runs the user started, and a general calculator.",
    "memory": "Long-term notes about the user: remember, recall, forget.",
    "web": "Fetch a public web page and search its text, links and headings",
    "ui": "Show the user where something is on the website (scroll to it and highlight it).",
}

# groups that are always published, whatever BLACKFOX_TOOL_GROUPS says (they need no data or keys)
ALWAYS_ON = ("ui",)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    fn: Callable
    group: str
    writes: bool


REGISTRY: dict[str, ToolSpec] = {}


def tool(group: str, writes: bool = False):
    def deco(fn: Callable) -> Callable:
        REGISTRY[fn.__name__] = ToolSpec(fn.__name__, fn, group, writes)
        return fn
    return deco


def load_all() -> dict[str, ToolSpec]:
    import importlib
    for m in TOOL_MODULES:
        importlib.import_module(f"{__package__}.{m}")
    return REGISTRY


def enabled_tools(groups: list[str]) -> list[ToolSpec]:
    return [t for t in load_all().values() if t.group in groups or t.group in ALWAYS_ON]
