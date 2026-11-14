"""python -m blackfox.mcp_server            HTTP on 127.0.0.1:8087 (needs BLACKFOX_MCP_TOKEN)
python -m blackfox.mcp_server --stdio    stdio transport (for local MCP clients)"""

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--stdio", action="store_true")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8087)
args = parser.parse_args()

if args.stdio:
    from .server import build_server
    build_server().run("stdio")
else:
    import uvicorn

    from .server import build_app
    uvicorn.run(build_app(), host=args.host, port=args.port, log_level="warning",
                server_header=False, proxy_headers=True, forwarded_allow_ips="127.0.0.1")
