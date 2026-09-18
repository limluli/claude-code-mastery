from datetime import datetime, time as dtime
from enum import Enum

from stock.logging import log


class MarketStatus(Enum):
    OPEN = "open"
    LUNCH = "lunch"
    CLOSED = "closed"


class MarketHours:
    """시장 운영시간 관리"""

    MARKET_OPEN = dtime(9, 0)
    MARKET_CLOSE = dtime(15, 30)
    LUNCH_START = dtime(11, 30)
    LUNCH_END = dtime(13, 0)

    # 한국거래소 휴장일 (간단한 예)
    HOLIDAYS = {
        (1, 1),  # 신년
        (3, 1),  # 삼일절
        (4, 10),  # 국회의원선거일
        (5, 5),  # 어린이날
        (5, 15),  # 부처님오신날
        (6, 6),  # 현충일
        (8, 15),  # 광복절
        (9, 16),  # 추석
        (9, 17),  # 추석
        (9, 18),  # 추석
        (10, 3),  # 개천절
        (10, 9),  # 한글날
        (12, 25),  # 크리스마스
    }

    @classmethod
    def get_status(cls) -> MarketStatus:
        """현재 시장 상태"""
        now = datetime.now()

        # 주말 체크
        if now.weekday() >= 5:
            return MarketStatus.CLOSED

        # 휴장일 체크
        if (now.month, now.day) in cls.HOLIDAYS:
            return MarketStatus.CLOSED

        now_time = now.time()

        # 장 시간 체크
        if now_time < cls.MARKET_OPEN or now_time > cls.MARKET_CLOSE:
            return MarketStatus.CLOSED

        # 점심시간 체크
        if cls.LUNCH_START <= now_time < cls.LUNCH_END:
            return MarketStatus.LUNCH

        return MarketStatus.OPEN

    @classmethod
    def is_market_open(cls) -> bool:
        """장 개장 중?"""
        return cls.get_status() == MarketStatus.OPEN

    @classmethod
    def time_to_market_close(cls) -> int:
        """장 종료까지 남은 시간 (초)"""
        now = datetime.now()
        close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        delta = close_time - now
        return max(0, int(delta.total_seconds()))
