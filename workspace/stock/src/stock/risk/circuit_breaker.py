from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from config.settings import settings
from stock.logging import log


class CircuitBreakerStatus(Enum):
    """서킷브레이커 상태"""

    GREEN = "green"  # 정상 (거래 가능)
    YELLOW = "yellow"  # 경고 (거래 주의)
    RED = "red"  # 중단 (거래 중지)


@dataclass
class RiskMetrics:
    """리스크 지표"""

    daily_pnl: float = 0.0  # 일일 손익
    daily_loss_limit: float = settings.daily_loss_limit  # 일일 손실 한도
    max_position_ratio: float = settings.max_position_ratio  # 종목당 최대 비중
    stop_loss_ratio: float = settings.stop_loss_ratio  # 손절 비율
    take_profit_ratio: float = settings.take_profit_ratio  # 익절 비율


class CircuitBreaker:
    """
    서킷브레이커

    1일 최대 손실 한도에 도달하면 매매를 자동 중지
    """

    def __init__(self):
        self.status = CircuitBreakerStatus.GREEN
        self.daily_loss_limit = settings.daily_loss_limit
        self.reset_time = self._get_reset_time()
        self.triggered_at: Optional[datetime] = None

    def _get_reset_time(self) -> datetime:
        """다음날 0시"""
        now = datetime.now()
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    def check_daily_loss(self, current_pnl: float) -> CircuitBreakerStatus:
        """
        일일 손실 확인

        Args:
            current_pnl: 현재 일일 손익

        Returns:
            CircuitBreakerStatus
        """
        # 매일 자정에 리셋
        if datetime.now() > self.reset_time:
            self.status = CircuitBreakerStatus.GREEN
            self.triggered_at = None
            self.reset_time = self._get_reset_time()

        # 손실 한도 체크
        if current_pnl <= self.daily_loss_limit:
            if self.status != CircuitBreakerStatus.RED:
                log.critical(
                    f"[CIRCUIT BREAKER] Daily loss limit exceeded! "
                    f"Current P&L: {current_pnl:,.0f} / Limit: {self.daily_loss_limit:,.0f}"
                )
                self.status = CircuitBreakerStatus.RED
                self.triggered_at = datetime.now()
        else:
            self.status = CircuitBreakerStatus.GREEN

        return self.status

    def is_trading_allowed(self) -> bool:
        """거래 가능 여부"""
        return self.status != CircuitBreakerStatus.RED

    def get_remaining_daily_loss(self, current_pnl: float) -> float:
        """남은 일일 손실 한도"""
        return self.daily_loss_limit - current_pnl


class PositionSizer:
    """
    포지션 사이징

    종목당 최대 비중을 초과하지 않도록 주문 수량을 제한
    """

    def __init__(self, account_balance: float = 1000000):
        self.account_balance = account_balance
        self.max_position_ratio = settings.max_position_ratio

    def calculate_position_size(
        self, stock_price: float, current_positions: dict
    ) -> int:
        """
        주문 수량 계산

        Args:
            stock_price: 종목 가격
            current_positions: 현재 보유 포지션 (종목코드: 수량)

        Returns:
            주문 가능 수량
        """
        # 최대 투자 금액 (계좌 잔고 * 최대 비중)
        max_position_value = self.account_balance * self.max_position_ratio

        # 주문 수량
        quantity = int(max_position_value / stock_price)

        log.debug(
            f"Position size calculated: {quantity} shares "
            f"@ {stock_price} = {quantity * stock_price:,.0f} "
            f"(max: {max_position_value:,.0f})"
        )

        return max(1, quantity)  # 최소 1주


class StopLossTakeProfitCalculator:
    """손절/익절 가격 계산"""

    @staticmethod
    def calculate_stops(entry_price: float) -> tuple:
        """
        손절/익절 가격 계산

        Args:
            entry_price: 진입 가격

        Returns:
            (stop_loss_price, take_profit_price)
        """
        stop_loss_ratio = settings.stop_loss_ratio
        take_profit_ratio = settings.take_profit_ratio

        stop_loss_price = entry_price * (1 - stop_loss_ratio)
        take_profit_price = entry_price * (1 + take_profit_ratio)

        log.debug(
            f"Stops calculated: SL={stop_loss_price:,.0f} (-{stop_loss_ratio*100:.1f}%), "
            f"TP={take_profit_price:,.0f} (+{take_profit_ratio*100:.1f}%)"
        )

        return stop_loss_price, take_profit_price


class RiskManager:
    """
    통합 리스크 관리자

    서킷브레이커, 포지션 사이징, 손절/익절을 종합적으로 관리
    """

    def __init__(self, account_balance: float = 1000000):
        self.circuit_breaker = CircuitBreaker()
        self.position_sizer = PositionSizer(account_balance)
        self.stop_calculator = StopLossTakeProfitCalculator()
        self.metrics = RiskMetrics()

    def check_can_trade(self, current_pnl: float) -> bool:
        """거래 가능 여부 확인"""
        self.circuit_breaker.check_daily_loss(current_pnl)
        return self.circuit_breaker.is_trading_allowed()

    def calculate_order_quantity(
        self, stock_price: float, current_positions: dict
    ) -> int:
        """주문 수량 계산"""
        return self.position_sizer.calculate_position_size(stock_price, current_positions)

    def calculate_stops(self, entry_price: float) -> tuple:
        """손절/익절 가격 계산"""
        return self.stop_calculator.calculate_stops(entry_price)

    def get_status(self, current_pnl: float) -> dict:
        """현재 리스크 상태"""
        self.circuit_breaker.check_daily_loss(current_pnl)

        return {
            "circuit_breaker_status": self.circuit_breaker.status.value,
            "is_trading_allowed": self.circuit_breaker.is_trading_allowed(),
            "daily_pnl": current_pnl,
            "daily_loss_limit": self.circuit_breaker.daily_loss_limit,
            "remaining_daily_loss": self.circuit_breaker.get_remaining_daily_loss(
                current_pnl
            ),
            "max_position_ratio": self.metrics.max_position_ratio,
        }


# 글로벌 리스크 관리자 인스턴스
risk_manager = RiskManager()
