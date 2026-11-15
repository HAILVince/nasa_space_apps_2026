"""show_on_page: the AI points at a part of the website; the browser scrolls there and highlights it."""

import asyncio
import json
from typing import get_args

from blackfox.harness.toolbox import QUICK_TOOLS, MCPToolbox
from blackfox.tools import enabled_tools
from blackfox.tools.ui_tools import PAGES, TARGETS, Target, show_on_page


def test_every_target_has_a_page_and_the_schema_lists_exactly_them():
    assert set(get_args(Target)) == set(TARGETS)
    assert {page for page, _ in TARGETS.values()} == set(PAGES)


def test_show_on_page_returns_the_action_the_browser_runs():
    out = show_on_page("gap_map", note="  Itt a   hiánytérkép ")
    assert out["action"] == {"type": "show", "page": "lab", "url": "/lab.html", "target": "gap_map",
                             "note": "Itt a hiánytérkép"}
    home = show_on_page("experiments")["action"]
    assert home["page"] == "home" and home["url"] == "/" and home["note"] == ""
    assert len(show_on_page("verdict", note="x" * 500)["action"]["note"]) == 120
    assert "error" in show_on_page("not_a_target")


def test_ui_tool_is_always_published_and_visible_without_opening_a_category():
    assert "show_on_page" in {t.name for t in enabled_tools(["design"])}      # even when groups are pinned
    assert "show_on_page" in QUICK_TOOLS

    async def run():
        async with MCPToolbox({"visitor_id": "v-ui"}, transport="inproc") as tb:
            visible = {t["function"]["name"] for t in tb.openai_tools()}
            schema = next(t for t in tb.openai_tools() if t["function"]["name"] == "show_on_page")["function"]
            out, err = await tb.call("show_on_page", {"target": "start_button"})
            bad, bad_err = await tb.call("show_on_page", {"target": "everything"})
            return visible, schema, json.loads(out), err, bad_err
    visible, schema, out, err, bad_err = asyncio.run(run())
    assert "show_on_page" in visible and len(schema["description"]) < 900       # never cut by the toolbox
    assert set(schema["parameters"]["properties"]["target"]["enum"]) == set(TARGETS)
    assert not err and out["action"]["target"] == "start_button" and bad_err
