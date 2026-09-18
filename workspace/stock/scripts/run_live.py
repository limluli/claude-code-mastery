#!/usr/bin/env python3
"""
Phase 4+: Live Trading with Paper/Live Mode

사용법:
  poetry run python scripts/run_live.py --mode paper --stock 005930 --strategy ma_cross
"""

import argparse
import sys
import signal
import time
from datetime import datetime, time as dtime

# Python path 설정
sys.path.insert(0, str(sys.path[0]))

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config.settings import settings
from stock.market_data.rest_client import kis_rest
from stock.market_data.data_manager import data_manager
from stock.strategy import StrategyFactory
from stock.execution.trade_manager import trade_manager
from stock.logging import log


class LiveTradingBot:
    """실거래 로봇"""

    MARKET_OPEN = dtime(9, 0)
    MARKET_CLOSE = dtime(15, 30)
    LUNCH_START = dtime(11, 30)
    LUNCH_END = dtime(13, 0)

    def __init__(self, mode: str, stock_code: str, strategy):
        self.mode = mode  # paper or live
        self.stock_code = stock_code
        self.strategy = strategy
        self.is_running = False

        mode_str = "모의투자" if mode == "paper" else "실거래"
        log.info(f"[START] 초기화 - {mode_str} 모드, 종목: {stock_code}, 전략: {strategy.name}")

    def is_market_open(self) -> bool:
        """시장 개장 여부 확인"""
        now = datetime.now().time()

        # 주말 체크 (사실은 거래소 휴장일 캘린더를 사용해야 함)
        today = datetime.now().weekday()
        if today >= 5:  # 토, 일요일
            return False

        if now < self.MARKET_OPEN or now > self.MARKET_CLOSE:
            return False

        if self.LUNCH_START <= now < self.LUNCH_END:
            return False

        return True

    def get_latest_data(self, bars: int = 20) -> bool:
        """최신 데이터 조회"""
        try:
            df = data_manager.load_daily_ohlcv(self.stock_code)

            if df.empty or len(df) < bars:
                log.warning(f"Insufficient data: {len(df)} bars")
                return False

            # 최근 N개 로우
            df = df.tail(bars)
            quote = kis_rest.get_quote(self.stock_code)

            if not quote:
                log.error("Failed to get current quote")
                return False

            log.debug(
                f"[DATA] {self.stock_code}: {quote['current_price']:,}원 "
                f"({quote['change_rate']:+.2f}%) vol: {quote['volume']:,}"
            )

            return True

        except Exception as e:
            log.error(f"Failed to get data: {e}")
            return False

    def execute_strategy(self) -> bool:
        """전략 실행"""
        try:
            # 데이터 로드
            df = data_manager.load_daily_ohlcv(self.stock_code)

            if df.empty or len(df) < 30:
                log.warning("Insufficient data for strategy")
                return False

            # 신호 생성
            signal = self.strategy.generate_signal(df)

            if signal.value != 0:  # BUY 또는 SELL
                # 현재가 조회
                quote = kis_rest.get_quote(self.stock_code)

                if not quote:
                    log.error("Failed to get quote for order")
                    return False

                # 주문 실행
                order = trade_manager.on_signal(signal, self.stock_code, quote)

                if order:
                    log.info(f"[ORDER] Submitted: {order.side.value} {order.quantity} @ {order.price}")
                    return True

        except Exception as e:
            log.error(f"Strategy execution error: {e}")
            import traceback

            traceback.print_exc()

        return False

    def print_status(self):
        """현재 상태 출력"""
        try:
            quote = kis_rest.get_quote(self.stock_code)

            if not quote:
                return

            position = trade_manager.get_current_position()
            daily_pnl = trade_manager.get_daily_pnl()

            log.info("-" * 60)
            log.info(
                f"[STATUS] {self.stock_code}: {quote['current_price']:,}원 "
                f"({quote['change_rate']:+.2f}%)"
            )

            if position:
                unrealized_pnl = position.unrealized_pnl
                unrealized_pnl_pct = position.unrealized_pnl_pct
                log.info(
                    f"  Position: {position.quantity} shares @ {position.entry_price:,.0f} "
                    f"(Unrealized: {unrealized_pnl:+,.0f} / {unrealized_pnl_pct:+.2f}%)"
                )

            log.info(f"  Daily P&L: {daily_pnl:+,.0f}")
            log.info(f"  Trades: {len(trade_manager.get_trade_history())}")
            log.info("-" * 60)

        except Exception as e:
            log.error(f"Error printing status: {e}")

    def run(self, duration_hours: int = 1):
        """
        실거래 실행

        Args:
            duration_hours: 실행 시간 (시간)
        """
        self.is_running = True
        start_time = datetime.now()
        check_interval = 60  # 1분마다 확인

        def signal_handler(sig, frame):
            log.info("\n[STOP] 정상 종료 중...")
            self.is_running = False

        signal.signal(signal.SIGINT, signal_handler)

        mode_str = "모의투자" if self.mode == "paper" else "실거래"
        log.info(f"[RUN] {mode_str} 시작 - {duration_hours}시간 동안 실행")

        try:
            while self.is_running:
                elapsed = (datetime.now() - start_time).total_seconds() / 3600

                if elapsed > duration_hours:
                    log.info(f"Duration limit reached ({duration_hours}h)")
                    break

                if not self.is_market_open():
                    # log.debug("Market is closed, waiting...")
                    time.sleep(60)
                    continue

                # 데이터 최신화
                if self.get_latest_data():
                    # 전략 실행
                    self.execute_strategy()

                # 상태 출력
                self.print_status()

                # 대기
                time.sleep(check_interval)

        except KeyboardInterrupt:
            log.info("Interrupted")

        finally:
            self.shutdown()

    def shutdown(self):
        """종료 처리"""
        # 미체결 포지션 정리
        position = trade_manager.get_current_position()

        if position:
            log.warning("[CLEANUP] 진행 중인 포지션을 매도하고 종료합니다...")
            quote = kis_rest.get_quote(self.stock_code)

            if quote:
                trade_manager._exit_position(quote["current_price"])

        # 최종 리포트
        history = trade_manager.get_trade_history()
        total_pnl = sum(t.realized_pnl for t in history)
        win_rate = trade_manager.get_win_rate()

        log.info("=" * 60)
        log.info("[END] 트레이딩 종료")
        log.info(f"  총 거래: {len(history)}")
        log.info(f"  총 손익: {total_pnl:+,.0f}원")

        if history:
            log.info(f"  승률: {win_rate:.1f}%")

        log.info("=" * 60)

        self.is_running = False


def main():
    parser = argparse.ArgumentParser(description="Live Trading Bot")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper", help="Trading mode")
    parser.add_argument("--stock", default="005930", help="Stock code")
    parser.add_argument("--strategy", default="ma_cross", help="Strategy (ma_cross, rsi)")
    parser.add_argument("--duration", type=int, default=24, help="Duration in hours (default: 24)")

    args = parser.parse_args()

    # 설정 검증
    if args.mode == "live" and settings.is_paper_mode:
        log.error("실거래 모드로 전환하려면 .env에서 TRADING_MODE=live로 설정하세요")
        return 1

    # 전략 생성
    try:
        if args.strategy == "ma_cross":
            strategy = StrategyFactory.create(
                "ma_cross", short_period=5, long_period=20
            )
        elif args.strategy == "rsi":
            strategy = StrategyFactory.create("rsi", period=14)
        else:
            log.error(f"Unknown strategy: {args.strategy}")
            return 1
    except Exception as e:
        log.error(f"Failed to create strategy: {e}")
        return 1

    # 트레이딩 봇 실행
    try:
        bot = LiveTradingBot(args.mode, args.stock, strategy)
        bot.run(args.duration)
        return 0

    except Exception as e:
        log.error(f"Trading bot error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
