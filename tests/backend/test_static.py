"""The frontend is served gzip-compressed (losslessly) and revalidated with ETags."""
import gzip

from fastapi.testclient import TestClient

from app.main import FRONTEND, app

client = TestClient(app)


def raw_get(path, **headers):
    """a request whose body is not decoded by the client, to see the bytes on the wire"""
    with client.stream("GET", path, headers=headers) as r:
        return r, b"".join(r.iter_raw())


def test_text_and_model_are_gzipped_losslessly():
    for path in ("/js/lab.js", "/css/app.css", "/lab.html", "/assets/3d/habitat.glb"):
        r, body = raw_get(path, **{"accept-encoding": "gzip, br"})
        assert r.status_code == 200 and r.headers["content-encoding"] == "gzip", path
        assert r.headers["cache-control"] == "no-cache" and r.headers["vary"] == "Accept-Encoding"
        assert gzip.decompress(body) == (FRONTEND / path.lstrip("/")).read_bytes(), path
    r, body = raw_get("/assets/3d/habitat.glb", **{"accept-encoding": "gzip"})
    assert len(body) < 0.4 * (FRONTEND / "assets/3d/habitat.glb").stat().st_size


def test_revalidation_returns_an_empty_304():
    r, _ = raw_get("/js/lab.js", **{"accept-encoding": "gzip"})
    again = client.get("/js/lab.js", headers={"accept-encoding": "gzip", "if-none-match": r.headers["etag"]})
    assert again.status_code == 304 and again.content == b""
    plain = client.get("/js/lab.js", headers={"accept-encoding": "identity"})
    assert plain.status_code == 200 and "content-encoding" not in plain.headers
    assert client.get("/js/lab.js", headers={"accept-encoding": "identity", "if-none-match": plain.headers["etag"]}).status_code == 304


def test_plain_file_without_gzip_for_images_ranges_and_old_clients():
    r, body = raw_get("/assets/3d/habitat_ao.webp", **{"accept-encoding": "gzip"})
    assert "content-encoding" not in r.headers and body == (FRONTEND / "assets/3d/habitat_ao.webp").read_bytes()
    r, body = raw_get("/js/lab.js", **{"accept-encoding": "identity"})
    assert "content-encoding" not in r.headers and body == (FRONTEND / "js/lab.js").read_bytes()
    r, body = raw_get("/js/lab.js", **{"accept-encoding": "gzip", "range": "bytes=0-9"})
    assert r.status_code == 206 and "content-encoding" not in r.headers and len(body) == 10
    head = client.head("/js/lab.js", headers={"accept-encoding": "gzip"})
    assert head.status_code == 200 and int(head.headers["content-length"]) > 0


def test_api_and_missing_files_are_unaffected():
    assert client.get("/api/health").status_code == 200
    r = client.get("/no-such-page.html")
    assert r.status_code == 404
