from __future__ import annotations

import argparse
import json

from platform_data.pipelines.fred_macro import refresh_fred_macro_core
from platform_data.pipelines.global_m2 import refresh_global_m2
from platform_data.pipelines.macro_dashboard import build_macro_dashboard
from platform_data.pipelines.market_detail import build_macro_market_detail
from platform_data.pipelines.treasury_macro import (
    refresh_treasury_10y,
    refresh_treasury_market_tenors,
)
from platform_data.pipelines.yahoo_macro import refresh_yahoo_macro_market


def main() -> int:
    parser = argparse.ArgumentParser(description="platform-data pipeline runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    treasury = subparsers.add_parser(
        "refresh-treasury-10y", help="refresh official U.S. Treasury 10Y data"
    )
    treasury.add_argument("--year", type=int, default=None)
    tenors = subparsers.add_parser(
        "refresh-treasury-market-tenors",
        help="refresh official U.S. Treasury 2Y/10Y/30Y data",
    )
    tenors.add_argument("--year", type=int, default=None)
    subparsers.add_parser(
        "build-macro-market-detail", help="build shared macro market-detail metrics"
    )
    subparsers.add_parser(
        "refresh-fred-macro-core", help="refresh approved FRED macro core series"
    )
    subparsers.add_parser(
        "refresh-yahoo-macro-market", help="refresh approved Yahoo macro instruments"
    )
    subparsers.add_parser(
        "build-macro-dashboard", help="build Macro V1 topic dashboard contract"
    )
    subparsers.add_parser(
        "refresh-global-m2", help="refresh the frozen five-region Global M2 proxy"
    )

    args = parser.parse_args()

    if args.command == "refresh-treasury-10y":
        result = refresh_treasury_10y(year=args.year)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "build-macro-market-detail":
        result = build_macro_market_detail()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-treasury-market-tenors":
        result = refresh_treasury_market_tenors(year=args.year)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-fred-macro-core":
        result = refresh_fred_macro_core()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-yahoo-macro-market":
        result = refresh_yahoo_macro_market()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "build-macro-dashboard":
        result = build_macro_dashboard()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-global-m2":
        result = refresh_global_m2()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
