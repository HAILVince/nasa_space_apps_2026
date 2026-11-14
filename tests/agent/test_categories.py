import asyncio
import json

from blackfox.harness.toolbox import MCPToolbox, OPEN_TOOL


def names(tb):
    return [t["function"]["name"] for t in tb.openai_tools()]


def test_tools_hidden_until_category_opened():
    async def go():
        async with MCPToolbox(transport="inproc", context={"visitor_id": "v"}) as tb:
            assert names(tb) == [OPEN_TOOL]
            out, err = await tb.call(OPEN_TOOL, {"category": "physics"})
            assert not err and "calculate" in json.loads(out)["tools"]
            n = names(tb)
            assert "calculate" in n and "get_design" not in n
            _, err = await tb.call(OPEN_TOOL, {"category": "nope"})
            assert err
            await tb.call("design_catalog", {})       # naming a tool opens its category
            assert "get_design" in names(tb)
    asyncio.run(go())
