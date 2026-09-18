from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

import pandas as pd
import numpy as np

from stock.strategy.base import Strategy, Signal
from stock.logging import log


@dataclass
class BacktestResult:
    """백테스트 결과"""

    total_return: float  # 수익률 (%)
    total_trades: int  # 총 거래 수
    winning_trades: int  # 수익 거래 수
    losing_trades: int  # 손실 거래 수
    win_rate: float  # 승률 (%)
    avg_win: float  # 평균 수익
    avg_loss: float  # 평균 손실
    max_drawdown: float  # 최대 낙폭 (%)
    sharpe_ratio: float  # 샤프 지수
    cumulative_returns: pd.Series  # 누적 수익률
    trades: List[dict]  # 거래 내역


class BacktestEngine:
    """
    백테스팅 엔진

    전략을 과거 데이터에서 검증하고 성과를 계산
    """

    def __init__(self, initial_capital: float = 1000000, commission: float = 0.0015):
        """
        Args:
            initial_capital: 초기 자본 (원)
            commission: 거래 수수료 (비율, 0.0015 = 0.15%)
        """
        self.initial_capital = initial_capital
        self.commission = commission  # 거래세 + 수수료

    def run(self, strategy: Strategy, df: pd.DataFrame) -> BacktestResult:
        """
        백테스팅 실행

        Args:
            strategy: 전략 인스턴스
            df: OHLCV 데이터프레임 (date/timestamp, open, high, low, close, volume)

        Returns:
            BacktestResult
        """
        if df.empty or len(df) < 2:
            log.error("Insufficient data for backtest")
            return None

        df = df.copy()
        df = df.sort_values("date" if "date" in df.columns else "timestamp").reset_index(drop=True)

        trades = []
        position = None  # 현재 진입 거래
        balance = self.initial_capital
        portfolio_values = [balance]
        dates = []

        for i in range(1, len(df)):
            current_bar = df.iloc[:i]
            signal = strategy.generate_signal(current_bar)
            price = df.iloc[i]["close"]
            date = df.iloc[i].get("date", df.iloc[i].get("timestamp"))

            dates.append(date)

            # 매수 신호
            if signal == Signal.BUY and position is None:
                # 수수료 반영
                shares = balance / price / (1 + self.commission)
                position = {
                    "entry_date": date,
                    "entry_price": price,
                    "shares": shares,
                    "exit_date": None,
                    "exit_price": None,
                    "profit": 0,
                    "profit_pct": 0,
                }
                balance -= shares * price * (1 + self.commission)
                log.debug(f"BUY @ {price} ({shares:.2f} shares) | Balance: {balance:,.0f}")

            # 매도 신호
            elif signal == Signal.SELL and position is not None:
                position["exit_date"] = date
                position["exit_price"] = price
                position["profit"] = (price - position["entry_price"]) * position["shares"]
                position["profit_pct"] = (price - position["entry_price"]) / position["entry_price"] * 100

                balance += position["shares"] * price * (1 - self.commission)
                trades.append(position)
                log.debug(
                    f"SELL @ {price} | P&L: {position['profit']:+,.0f} "
                    f"({position['profit_pct']:+.2f}%)"
                )
                position = None

            # 현재 포트폴리오 가치 계산
            if position is not None:
                unrealized = position["shares"] * price
                current_value = balance + unrealized
            else:
                current_value = balance

            portfolio_values.append(current_value)

        # 종료 시 미체결 거래 정리
        if position is not None:
            position["exit_date"] = df.iloc[-1].get("date", df.iloc[-1].get("timestamp"))
            position["exit_price"] = df.iloc[-1]["close"]
            position["profit"] = (position["exit_price"] - position["entry_price"]) * position["shares"]
            position["profit_pct"] = (
                (position["exit_price"] - position["entry_price"]) / position["entry_price"] * 100
            )
            balance += position["shares"] * position["exit_price"] * (1 - self.commission)
            trades.append(position)

        # 성과 지표 계산
        result = self._calculate_metrics(
            portfolio_values, trades, dates, self.initial_capital
        )
        result.trades = trades

        return result

    @staticmethod
    def _calculate_metrics(
        portfolio_values: List[float],
        trades: List[dict],
        dates: List,
        initial_capital: float,
    ) -> BacktestResult:
        """성과 지표 계산"""

        # 수익률
        final_value = portfolio_values[-1]
        total_return = (final_value - initial_capital) / initial_capital * 100

        # 거래 통계
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t["profit"] > 0)
        losing_trades = sum(1 for t in trades if t["profit"] < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        avg_win = sum(t["profit"] for t in trades if t["profit"] > 0) / winning_trades if winning_trades > 0 else 0
        avg_loss = sum(t["profit"] for t in trades if t["profit"] < 0) / losing_trades if losing_trades > 0 else 0

        # 최대 낙폭
        cumulative = pd.Series(portfolio_values)
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100

        # 샤프 지수 (간단히 계산)
        returns = pd.Series(portfolio_values).pct_change().fillna(0)
        sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

        cumulative_returns = (cumulative / initial_capital - 1) * 100

        return BacktestResult(
            total_return=total_return,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            cumulative_returns=cumulative_returns,
            trades=[],
        )


# 글로벌 백테스팅 엔진 인스턴스
backtest_engine = BacktestEngine()
