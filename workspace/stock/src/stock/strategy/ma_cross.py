import pandas as pd

from .base import Strategy, Signal, StrategyFactory
from stock.logging import log


class MACrossStrategy(Strategy):
    """
    Moving Average Crossover 전략

    단기 이동평균이 장기 이동평균을 상향돌파하면 매수,
    단기 이동평균이 장기 이동평균을 하향돌파하면 매도
    """

    def __init__(self, short_period: int = 5, long_period: int = 20):
        super().__init__("MA_CROSS")
        self.short_period = short_period
        self.long_period = long_period
        self.min_rows = max(short_period, long_period) + 1

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        """
        이평선 교차 신호 생성

        Args:
            df: OHLCV 데이터프레임

        Returns:
            Signal.BUY (골든 크로스), Signal.SELL (데드 크로스), Signal.NONE
        """
        if not self.validate_data(df, self.min_rows):
            log.warning(f"Insufficient data for {self.name} (need {self.min_rows}, got {len(df)})")
            return Signal.NONE

        # 이동평균 계산
        df = df.copy()
        df["sma_short"] = df["close"].rolling(self.short_period).mean()
        df["sma_long"] = df["close"].rolling(self.long_period).mean()

        # 최근 2개 로우 확인
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        # 현재 이평선이 유효한지 확인
        if pd.isna(curr["sma_short"]) or pd.isna(curr["sma_long"]):
            return Signal.NONE

        # 골든 크로스: 단기 > 장기로 올라옴
        if prev["sma_short"] <= prev["sma_long"] and curr["sma_short"] > curr["sma_long"]:
            log.info(
                f"[{self.name}] Golden Cross - Buy Signal "
                f"(SMA{self.short_period}: {curr['sma_short']:.2f}, "
                f"SMA{self.long_period}: {curr['sma_long']:.2f})"
            )
            self.last_signal = Signal.BUY
            return Signal.BUY

        # 데드 크로스: 단기 < 장기로 내려옴
        if prev["sma_short"] >= prev["sma_long"] and curr["sma_short"] < curr["sma_long"]:
            log.info(
                f"[{self.name}] Dead Cross - Sell Signal "
                f"(SMA{self.short_period}: {curr['sma_short']:.2f}, "
                f"SMA{self.long_period}: {curr['sma_long']:.2f})"
            )
            self.last_signal = Signal.SELL
            return Signal.SELL

        return Signal.NONE


class RSIStrategy(Strategy):
    """
    Relative Strength Index (RSI) 전략

    RSI > 70: 과매수 → 매도 신호
    RSI < 30: 과매도 → 매수 신호
    """

    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        super().__init__("RSI")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        self.min_rows = period + 1

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        """
        RSI 신호 생성

        Args:
            df: OHLCV 데이터프레임

        Returns:
            Signal.BUY (과매도), Signal.SELL (과매수), Signal.NONE
        """
        if not self.validate_data(df, self.min_rows):
            log.warning(f"Insufficient data for {self.name} (need {self.min_rows}, got {len(df)})")
            return Signal.NONE

        # RSI 계산
        df = df.copy()
        df["delta"] = df["close"].diff()
        df["gain"] = df["delta"].clip(lower=0)
        df["loss"] = -df["delta"].clip(upper=0)

        avg_gain = df["gain"].rolling(self.period).mean()
        avg_loss = df["loss"].rolling(self.period).mean()

        rs = avg_gain / avg_loss
        df["rsi"] = 100 - (100 / (1 + rs))

        curr_rsi = df["rsi"].iloc[-1]

        if pd.isna(curr_rsi):
            return Signal.NONE

        # 과매도 → 매수
        if curr_rsi < self.oversold:
            log.info(f"[{self.name}] Oversold - Buy Signal (RSI: {curr_rsi:.2f})")
            self.last_signal = Signal.BUY
            return Signal.BUY

        # 과매수 → 매도
        if curr_rsi > self.overbought:
            log.info(f"[{self.name}] Overbought - Sell Signal (RSI: {curr_rsi:.2f})")
            self.last_signal = Signal.SELL
            return Signal.SELL

        return Signal.NONE


# 팩토리에 전략 등록
StrategyFactory.register("ma_cross", MACrossStrategy)
StrategyFactory.register("rsi", RSIStrategy)
