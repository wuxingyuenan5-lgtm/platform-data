from __future__ import annotations

import argparse
import json

from platform_data.pipelines.treasury_macro import refresh_treasury_10y
from platform_data.pipelines.market_detail import build_macro_market_detail


def main() -> int:
    parser = argparse.ArgumentParser(description="platform-data pipeline runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    treasury = subparsers.add_parser("refresh-treasury-10y", help="refresh official U.S. Treasury 10Y data")
    treasury.add_argument("--year", type=int, default=None)
    subparsers.add_parser("build-macro-market-detail", help="build shared macro market-detail metrics")

    args = parser.parse_args()

    if args.command == "refresh-treasury-10y":
        result = refresh_treasury_10y(year=args.year)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "build-macro-market-detail":
        result = build_macro_market_detail()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
