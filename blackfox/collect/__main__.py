"""Command line for the knowledge-base collector. Run `python -m blackfox.collect -h`."""

import argparse
import json
import sys
import threading
import time
from pathlib import Path

from ..settings import get_settings


def _harvest(args) -> int:
    from .sources import SOURCES, Http, Progress
    staging = Path(args.work) / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    http, failed = Http(), []
    for name in args.sources.split(","):
        name = name.strip()
        if name not in SOURCES:
            print(f"unknown source '{name}' (have: {', '.join(SOURCES)})")
            return 2
        progress = Progress(staging / f"{name}.progress.json")
        lock, count, t0 = threading.Lock(), [0], time.time()
        with open(staging / f"{name}.jsonl", "a", encoding="utf-8") as out:
            def sink(records, out=out, lock=lock, count=count):
                with lock:
                    for r in records:
                        out.write(json.dumps(r, ensure_ascii=False) + "\n")
                    out.flush()
                    count[0] += len(records)
            try:
                SOURCES[name](http, sink, progress)
            except Exception as e:   # one broken source must not lose the others; rerun to continue
                failed.append(name)
                print(f"{name}: stopped after {count[0]} records: {type(e).__name__}: {e}", flush=True)
            finally:
                progress.save()
        print(f"{name}: +{count[0]} records in {time.time() - t0:.0f}s", flush=True)
    if failed:
        print("incomplete sources (run harvest again to continue): " + ", ".join(failed))
    return 1 if failed else 0


def _build(args) -> int:
    from .build import build
    stats = build(Path(args.work) / "staging", Path(args.out), max_bytes=int(args.max_gb * 1e9))
    print(json.dumps(stats, indent=1))
    return 0


def _fulltext(args) -> int:
    from .fulltext import collect_fulltext
    stats = collect_fulltext(Path(args.knowledge), Path(args.fulltext_out), max_bytes=int(args.max_gb * 1e9),
                             workers=args.workers, limit=args.limit)
    print(json.dumps(stats, indent=1))
    return 0


def main(argv=None) -> int:
    s = get_settings()
    p = argparse.ArgumentParser(prog="python -m blackfox.collect", description=__doc__)
    p.add_argument("--work", default=str(s.data_dir / "collect"), help="working folder for downloaded raw records")
    p.add_argument("--max-gb", type=float, default=30.0, help="never let the database grow past this size (default 30)")
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest", help="download records from the sources")
    b = sub.add_parser("build", help="classify, sort and write the JSON database")
    a = sub.add_parser("all", help="harvest + build")
    f = sub.add_parser("fulltext", help="download full texts for the records in the database")
    for x in (h, a):
        x.add_argument("--sources", default="ntrs,epmc,arxiv,techport,osdr,wikipedia")
    for x in (b, a):
        x.add_argument("--out", default=str(s.knowledge_dir), help="database folder to write")
    f.add_argument("--knowledge", default=str(s.knowledge_dir), help="database folder to read")
    f.add_argument("--fulltext-out", default=str(s.fulltext_dir), help="folder for the full texts")
    f.add_argument("--workers", type=int, default=6)
    f.add_argument("--limit", type=int, default=0, help="stop after this many documents (0 = until --max-gb)")
    args = p.parse_args(argv)
    if args.cmd == "harvest":
        return _harvest(args)
    if args.cmd == "build":
        return _build(args)
    if args.cmd == "fulltext":
        return _fulltext(args)
    return _harvest(args) or _build(args)


if __name__ == "__main__":
    sys.exit(main())
