"""Offline scripts that build flame/data/. Run `python -m flame.ingest -h`."""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m flame.ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("psi", help="fetch the PSI combustion investigations")
    p.add_argument("--dry-run", action="store_true", help="print the rows, write nothing")
    sub.add_parser("papers", help="look up NTRS abstracts for the publications PSI lists")
    p = sub.add_parser("extract", help="ask the LLM for test envelopes and summaries (needs BLACKFOX_AI_KEY)")
    p.add_argument("--only", default="", help="comma-separated accessions, e.g. PSI-25,PSI-69")
    sub.add_parser("clean", help="clean the raw PSI tables into flame/data/psi_tests.json and flame/data/clean/")
    sub.add_parser("verify", help="check every envelope against the PSI tables and the cited NASA documents")
    args = parser.parse_args()
    if args.command == "psi":
        from . import psi
        return psi.main(dry_run=args.dry_run)
    if args.command == "papers":
        from . import papers
        return papers.main()
    if args.command == "extract":
        from . import extract
        return extract.main(only=[a.strip() for a in args.only.split(",") if a.strip()] or None)
    if args.command == "clean":
        from . import clean_tables
        return clean_tables.main()
    if args.command == "verify":
        from . import verify
        return verify.main()
    return 2


if __name__ == "__main__":
    sys.exit(main())
