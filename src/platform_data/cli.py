from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from platform_data.local_database import sync_local_database
from platform_data.pipelines.binance_crypto import refresh_binance_crypto_core
from platform_data.pipelines.cftc_commodity import refresh_cftc_commodity_core
from platform_data.pipelines.chinabond_macro import refresh_chinabond_market_tenors
from platform_data.pipelines.commodity_dashboard import build_commodity_dashboard
from platform_data.pipelines.crypto_dashboard import build_crypto_dashboard
from platform_data.pipelines.eia_commodity import refresh_eia_commodity_core
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
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="local data root (defaults to PLATFORM_DATA_ROOT or the repository root)",
    )
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
    subparsers.add_parser(
        "refresh-chinabond-market-tenors",
        help="refresh official China 2Y/10Y/30Y yields",
    )
    subparsers.add_parser(
        "refresh-cftc-commodity-core",
        help="refresh official CFTC commodity positioning",
    )
    subparsers.add_parser(
        "build-commodity-dashboard", help="build Commodity V1 dashboard contract"
    )
    subparsers.add_parser(
        "refresh-eia-commodity-core",
        help="refresh official EIA weekly petroleum inventories",
    )
    subparsers.add_parser(
        "refresh-binance-crypto-core",
        help="refresh Binance BTC/ETH spot and USD-M derivatives",
    )
    subparsers.add_parser(
        "build-crypto-dashboard", help="build Crypto V1 dashboard contract"
    )
    subparsers.add_parser(
        "sync-local-database", help="rebuild the local DuckDB mirror from canonical JSON"
    )

    args = parser.parse_args()
    data_root = args.data_root or Path(os.getenv("PLATFORM_DATA_ROOT", Path.cwd()))

    if args.command == "refresh-treasury-10y":
        result = refresh_treasury_10y(root=data_root, year=args.year)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "build-macro-market-detail":
        result = build_macro_market_detail(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-treasury-market-tenors":
        result = refresh_treasury_market_tenors(root=data_root, year=args.year)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-fred-macro-core":
        result = refresh_fred_macro_core(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-yahoo-macro-market":
        result = refresh_yahoo_macro_market(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "build-macro-dashboard":
        result = build_macro_dashboard(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-global-m2":
        result = refresh_global_m2(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-chinabond-market-tenors":
        result = refresh_chinabond_market_tenors(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-cftc-commodity-core":
        result = refresh_cftc_commodity_core(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "build-commodity-dashboard":
        result = build_commodity_dashboard(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-eia-commodity-core":
        result = refresh_eia_commodity_core(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "refresh-binance-crypto-core":
        result = refresh_binance_crypto_core(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "build-crypto-dashboard":
        result = build_crypto_dashboard(root=data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "sync-local-database":
        result = sync_local_database(data_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
