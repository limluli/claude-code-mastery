#!/usr/bin/env python3
"""
Phase 3 테스트: 백테스팅으로 전략 검증

사용법:
  poetry run python scripts/run_backtest.py --strategy ma_cross --stock 005930 --start-date 2023-01-01 --end-date 2024-01-01
"""

import argparse
import sys
from datetime import datetime

# Python path 설정
sys.path.insert(0, str(sys.path[0]))

from stock.backtest.runner import backtest_engine
from stock.strategy import StrategyFactory
from stock.market_data.data_manager import data_manager
from stock.logging import log


def print_backtest_report(result, strategy_name: str, stock_code: str, dates: str):
    """백테스트 결과 리포트 출력"""
    log.info("=" * 70)
    log.info(f"BACKTEST REPORT - {strategy_name} ({stock_code})")
    log.info(f"Period: {dates}")
    log.info("=" * 70)

    log.info(f"Initial Capital:       1,000,000 원")
    log.info(f"Final Portfolio Value: {result.cumulative_returns.iloc[-1] * 10000 + 1000000:,.0f} 원")
    log.info("")

    log.info(f"Total Return:          {result.total_return:+.2f}%")
    log.info(f"Max Drawdown:          {result.max_drawdown:.2f}%")
    log.info(f"Sharpe Ratio:          {result.sharpe_ratio:.2f}")
    log.info("")

    log.info(f"Total Trades:          {result.total_trades}")
    log.info(f"Winning Trades:        {result.winning_trades} ({result.win_rate:.1f}%)")
    log.info(f"Losing Trades:         {result.losing_trades}")

    if result.total_trades > 0:
        log.info(f"Avg Winning Trade:     {result.avg_win:+,.0f} 원")
        log.info(f"Avg Losing Trade:      {result.avg_loss:+,.0f} 원")
        log.info("")

        profit_factor = abs(result.avg_win / result.avg_loss) if result.avg_loss != 0 else float("inf")
        log.info(f"Profit Factor:         {profit_factor:.2f}")

    log.info("=" * 70)

    # 개별 거래 내역 (최근 10개)
    if result.trades:
        log.info("\nRecent Trades (Last 10):")
        log.info("-" * 70)
        for trade in result.trades[-10:]:
            log.info(
                f"Entry: {trade['entry_date'].strftime('%Y-%m-%d')} @ {trade['entry_price']:,} | "
                f"Exit: {trade['exit_date'].strftime('%Y-%m-%d')} @ {trade['exit_price']:,} | "
                f"P&L: {trade['profit']:+,.0f} ({trade['profit_pct']:+.2f}%)"
            )


def main():
    parser = argparse.ArgumentParser(description="Backtest Strategy")
    parser.add_argument("--strategy", default="ma_cross", help="Strategy name (ma_cross, rsi)")
    parser.add_argument("--stock", default="005930", help="Stock code (default: 005930)")
    parser.add_argument(
        "--start-date", default="2023-01-01", help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument("--end-date", default="2024-01-01", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--capital", type=float, default=1000000, help="Initial capital (default: 1,000,000)"
    )

    args = parser.parse_args()

    log.info("=" * 70)
    log.info("Phase 3: Strategy Validation with Backtest")
    log.info("=" * 70)

    # 1. 데이터 로드
    log.info(f"\nLoading {args.stock} data from {args.start_date} to {args.end_date}...")
    df = data_manager.load_daily_ohlcv(args.stock, args.start_date, args.end_date)

    if df.empty:
        log.error(f"No data found for {args.stock}")
        log.error(f"Have you run 'poetry run python scripts/test_market_data.py --stock {args.stock}'?")
        return 1

    log.info(f"✓ Loaded {len(df)} bars")

    # 2. 전략 생성
    try:
        if args.strategy == "ma_cross":
            strategy = StrategyFactory.create("ma_cross", short_period=5, long_period=20)
        elif args.strategy == "rsi":
            strategy = StrategyFactory.create("rsi", period=14)
        else:
            log.error(f"Unknown strategy: {args.strategy}")
            log.error(f"Available strategies: {StrategyFactory.get_available()}")
            return 1

        log.info(f"✓ Created strategy: {strategy.name}")
    except Exception as e:
        log.error(f"Failed to create strategy: {e}")
        return 1

    # 3. 백테스트 실행
    log.info("\nRunning backtest...")
    try:
        # 백테스팅 엔진 생성 (수수료 0.15% 반영)
        engine = backtest_engine
        result = engine.run(strategy, df)

        if result is None:
            log.error("Backtest failed")
            return 1

        # 결과 리포트
        print_backtest_report(
            result, strategy.name, args.stock, f"{args.start_date} ~ {args.end_date}"
        )

        # 4. 판정
        if result.total_trades > 0 and result.total_return > 0:
            log.info("\n✓ Phase 3 Complete Criteria Met!")
            log.info("  - Strategy generates signals: OK")
            log.info("  - Positive return in backtest: OK")
            log.info(f"  - Recommendation: Ready for paper trading validation")
            return 0
        elif result.total_trades > 0:
            log.warning(
                "\n⚠ Strategy generates signals but negative return in this period"
            )
            log.warning("  Recommendation: Try different parameters or longer test period")
            return 0  # 신호는 생성하므로 계속 진행 가능
        else:
            log.warning("\n⚠ Strategy did not generate any trades")
            log.warning("  Recommendation: Adjust strategy parameters")
            return 0

    except Exception as e:
        log.error(f"Backtest error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
