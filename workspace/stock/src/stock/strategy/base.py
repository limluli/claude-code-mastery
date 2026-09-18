from abc import ABC, abstractmethod
from typing import Optional
from enum import Enum

import pandas as pd


class Signal(Enum):
    """매매 신호"""

    NONE = 0  # 신호 없음
    BUY = 1  # 매수
    SELL = -1  # 매도


class Strategy(ABC):
    """
    전략의 기본 인터페이스

    모든 전략은 이 클래스를 상속하고 generate_signal 메서드를 구현해야 함
    """

    def __init__(self, name: str):
        self.name = name
        self.last_signal = Signal.NONE

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> Signal:
        """
        OHLCV 데이터를 받아 매매 신호 생성

        Args:
            df: OHLCV 데이터프레임 (columns: open, high, low, close, volume)
               최소 필요한 로우 수는 전략마다 다름

        Returns:
            Signal.BUY, Signal.SELL, 또는 Signal.NONE
        """
        pass

    def validate_data(self, df: pd.DataFrame, min_rows: int = 1) -> bool:
        """데이터 검증"""
        if df is None or df.empty:
            return False
        if len(df) < min_rows:
            return False
        required_cols = {"open", "high", "low", "close", "volume"}
        if not required_cols.issubset(df.columns):
            return False
        return True


class StrategyFactory:
    """전략 생성 팩토리"""

    _strategies = {}

    @classmethod
    def register(cls, name: str, strategy_class):
        """전략 등록"""
        cls._strategies[name] = strategy_class

    @classmethod
    def create(cls, name: str, **kwargs) -> Strategy:
        """전략 생성"""
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}")
        return cls._strategies[name](**kwargs)

    @classmethod
    def get_available(cls) -> list:
        """등록된 전략 목록"""
        return list(cls._strategies.keys())
