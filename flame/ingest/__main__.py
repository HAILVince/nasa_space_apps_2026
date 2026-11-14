"""Offline scripts that build flame/data/. Run `python -m flame.ingest -h`."""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m flame.ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("psi", help="fetch the PSI combustion investigations")
    p.add_argument("--dry-run", action="store_true", help="print the rows, write nothing")
    sub.add_parser("papers", help="look up NTRS abstracts for the publications PSI lists")
    args = parser.parse_args()
    if args.command == "psi":
        from . import psi
        return psi.main(dry_run=args.dry_run)
    if args.command == "papers":
        from . import papers
        return papers.main()
    return 2


if __name__ == "__main__":
    sys.exit(main())
