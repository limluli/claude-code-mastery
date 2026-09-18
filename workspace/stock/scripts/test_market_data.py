#!/usr/bin/env python3
"""
Phase 2 테스트: 시세 데이터 수집 검증

사용법:
  poetry run python scripts/test_market_data.py --stock 005930 --days 365
"""

import argparse
import sys
from datetime import datetime, timedelta

# Python path 설정
sys.path.insert(0, str(sys.path[0]))

import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from stock.market_data.rest_client import kis_rest
from stock.market_data.data_manager import data_manager
from stock.logging import log


def test_daily_ohlcv(stock_code: str, days: int = 365):
    """
    일봉 데이터 다운로드 테스트

    Args:
        stock_code: 종목코드
        days: 조회 기간 (일)
    """
    log.info(f"Testing daily OHLCV download for {stock_code} (last {days} days)...")

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    try:
        # REST API로 데이터 다운로드
        df = kis_rest.get_daily_ohlcv(stock_code, start_date=start_date, end_date=end_date, count=100)

        if df.empty:
            log.error(f"✗ Failed to download daily OHLCV for {stock_code}")
            return False

        log.info(f"✓ Downloaded {len(df)} daily bars for {stock_code}")
        log.info(f"  Date range: {df['date'].min()} ~ {df['date'].max()}")
        log.info(f"  Price range: {df['low'].min()} ~ {df['high'].max()}")
        log.info(f"  Volume: {df['volume'].sum():,}")

        # 데이터 저장
        data_manager.save_daily_ohlcv(stock_code, df)

        return True

    except Exception as e:
        log.error(f"✗ Exception: {e}")
        return False


def test_quote(stock_code: str):
    """
    현재가 조회 테스트

    Args:
        stock_code: 종목코드
    """
    log.info(f"Testing quote for {stock_code}...")

    try:
        quote = kis_rest.get_quote(stock_code)

        if not quote:
            log.error(f"✗ Failed to get quote for {stock_code}")
            return False

        log.info(f"✓ Got quote for {stock_code}")
        log.info(f"  Current: {quote['current_price']:,}원")
        log.info(f"  Change: {quote['change_rate']:+.2f}%")
        log.info(f"  Volume: {quote['volume']:,}")

        # 저장
        data_manager.save_quote(stock_code, quote)

        return True

    except Exception as e:
        log.error(f"✗ Exception: {e}")
        return False


def test_data_load(stock_code: str):
    """
    저장된 데이터 로드 테스트

    Args:
        stock_code: 종목코드
    """
    log.info(f"Testing data load for {stock_code}...")

    try:
        df = data_manager.load_daily_ohlcv(stock_code, start_date="2024-01-01")

        if df.empty:
            log.warning(f"No data found for {stock_code} from 2024-01-01")
            return False

        log.info(f"✓ Loaded {len(df)} bars from local storage")
        log.info(f"  First: {df.iloc[0]['date'].strftime('%Y-%m-%d')} {df.iloc[0]['close']}원")
        log.info(f"  Last: {df.iloc[-1]['date'].strftime('%Y-%m-%d')} {df.iloc[-1]['close']}원")

        return True

    except Exception as e:
        log.error(f"✗ Exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Phase 2 Market Data Test")
    parser.add_argument("--stock", default="005930", help="Stock code (default: 005930=Samsung Electronics)")
    parser.add_argument("--days", type=int, default=365, help="Number of days to fetch (default: 365)")
    parser.add_argument("--skip-download", action="store_true", help="Skip download, only load local data")

    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Phase 2: Market Data Collection Test")
    log.info("=" * 60)

    # 1. 현재가 조회
    success1 = test_quote(args.stock)

    # 2. 일봉 데이터 다운로드 및 저장
    if not args.skip_download:
        success2 = test_daily_ohlcv(args.stock, args.days)
    else:
        log.info("Skipping download (--skip-download)")
        success2 = True

    # 3. 저장된 데이터 로드
    success3 = test_data_load(args.stock)

    # 결과
    log.info("=" * 60)
    if success1 and success2 and success3:
        log.info("✓ Phase 2 Complete Criteria Met!")
        log.info("  - Quote retrieval: OK")
        log.info("  - Daily OHLCV download: OK")
        log.info("  - Data persistence: OK")
        log.info("=" * 60)
        return 0
    else:
        log.error("✗ Phase 2 Test Failed")
        log.error(f"  - Quote retrieval: {'OK' if success1 else 'FAILED'}")
        log.error(f"  - Daily OHLCV download: {'OK' if success2 else 'FAILED'}")
        log.error(f"  - Data persistence: {'OK' if success3 else 'FAILED'}")
        log.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
