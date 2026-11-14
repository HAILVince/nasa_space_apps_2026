"""The frontend's static files, compressed once and revalidated cheaply.

- Text-like files (scripts, styles, pages, JSON, SVG and the 3D model) are gzip-compressed at
  level 9 the first time they are asked for and kept in memory until the file changes; every
  later request gets the same bytes without compressing again. Gzip is lossless: the browser
  receives exactly the original file. The 3.4 MB habitat model goes over the wire as ~1 MB.
- Every response says `Cache-Control: no-cache`: the browser keeps its copy but asks whether it
  is still current, and gets an empty 304 when it is. A deploy is therefore picked up on the
  next load (the files have fixed names, so long-lived caching could serve stale copies).
- Images, fonts and other already-compressed formats are sent unchanged. Range requests, and
  clients that do not accept gzip, get the plain file.

Behind nginx (deploy/nginx-blackfox-locations.conf) the gzip response passes through as is.
"""
from __future__ import annotations

import gzip
import os
import threading

import anyio
from starlette.datastructures import Headers
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

COMPRESSIBLE = {".html", ".js", ".mjs", ".css", ".json", ".svg", ".glb", ".txt", ".csv", ".map", ".xml"}
MIN_BYTES = 1024
CACHE_CONTROL = "no-cache"


class CompressedStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gz: dict[str, tuple[int, int, bytes]] = {}       # path -> (mtime_ns, size, gzip bytes)
        self._lock = threading.Lock()

    def _compressed(self, path: str, st: os.stat_result) -> bytes:
        hit = self._gz.get(path)
        if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
            return hit[2]
        with open(path, "rb") as f:
            raw = f.read()
        body = gzip.compress(raw, compresslevel=9, mtime=0)      # mtime=0: same bytes every time
        with self._lock:
            self._gz[path] = (st.st_mtime_ns, st.st_size, body)
        return body

    def warm(self) -> None:
        """compress every eligible file ahead of the first request (run in a background thread)"""
        for directory in self.all_directories:
            for root, _, files in os.walk(directory):
                for name in files:
                    full = os.path.join(root, name)
                    try:
                        st = os.stat(full)
                        if os.path.splitext(name)[1].lower() in COMPRESSIBLE and st.st_size >= MIN_BYTES:
                            self._compressed(full, st)
                    except OSError:
                        continue

    async def get_response(self, path: str, scope: Scope) -> Response:
        resp = await super().get_response(path, scope)
        resp.headers["cache-control"] = CACHE_CONTROL
        if not isinstance(resp, FileResponse) or resp.status_code != 200:
            return resp
        full, st = str(resp.path), resp.stat_result
        if os.path.splitext(full)[1].lower() not in COMPRESSIBLE or st is None or st.st_size < MIN_BYTES:
            return resp
        resp.headers["vary"] = "Accept-Encoding"
        req = Headers(scope=scope)
        if "gzip" not in req.get("accept-encoding", "").lower() or "range" in req:
            return resp
        etag = resp.headers["etag"]
        gz_etag = etag[:-1] + '-gz"' if etag.endswith('"') else etag + "-gz"
        headers = {"etag": gz_etag, "last-modified": resp.headers["last-modified"], "cache-control": CACHE_CONTROL,
                   "vary": "Accept-Encoding", "content-encoding": "gzip", "content-type": resp.headers["content-type"]}
        if gz_etag in [t.strip() for t in req.get("if-none-match", "").split(",")]:
            return Response(status_code=304, headers={k: v for k, v in headers.items() if k != "content-type"})
        body = await anyio.to_thread.run_sync(self._compressed, full, st)
        if scope["method"] == "HEAD":
            return Response(b"", headers={**headers, "content-length": str(len(body))})
        return Response(body, headers=headers)
