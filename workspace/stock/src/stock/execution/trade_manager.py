from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict
from enum import Enum

from stock.execution.order import Order, OrderSide, OrderStatus, order_executor
from stock.market_data.rest_client import kis_rest
from stock.strategy.base import Signal
from stock.logging import log


class TradeState(Enum):
    """거래 상태"""

    IDLE = "idle"  # 진입 가능
    LONG = "long"  # 롱 포지션 보유 중
    EXIT_SIGNAL = "exit_signal"  # 매도 신호 받음


@dataclass
class Trade:
    """거래 기록"""

    stock_code: str
    entry_price: float
    entry_time: datetime
    entry_order: Order
    quantity: int

    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_order: Optional[Order] = None

    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    @property
    def unrealized_pnl(self) -> float:
        """미실현 손익"""
        if self.exit_price is None:
            # 현재가 조회
            quote = kis_rest.get_quote(self.stock_code)
            current_price = quote.get("current_price", self.entry_price)
        else:
            current_price = self.exit_price

        return (current_price - self.entry_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        """미실현 손익률 (%)"""
        if self.entry_price == 0:
            return 0.0
        return (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100

    @property
    def realized_pnl(self) -> float:
        """실현 손익"""
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.quantity

    @property
    def realized_pnl_pct(self) -> float:
        """실현 손익률 (%)"""
        if self.entry_price == 0:
            return 0.0
        return (self.realized_pnl / (self.entry_price * self.quantity)) * 100


class TradeManager:
    """
    거래 관리자

    진입/청산 신호를 받아 실제 주문을 생성하고 거래 상태를 관리
    """

    def __init__(self):
        self.state = TradeState.IDLE
        self.current_trade: Optional[Trade] = None
        self.completed_trades: list = []

        self.executor = order_executor

    def on_signal(self, signal: Signal, stock_code: str, quote: dict) -> Optional[Order]:
        """
        전략 신호 처리

        Args:
            signal: 매매 신호 (BUY/SELL/NONE)
            stock_code: 종목 코드
            quote: 현재가 정보

        Returns:
            생성된 Order 또는 None
        """
        current_price = quote.get("current_price", 0)

        if signal == Signal.BUY and self.state == TradeState.IDLE:
            return self._enter_position(stock_code, current_price, quote)

        elif signal == Signal.SELL and self.state == TradeState.LONG:
            return self._exit_position(current_price)

        elif signal == Signal.NONE and self.state == TradeState.LONG:
            # 손절/익절 체크
            self._check_stop_loss_take_profit(current_price)

        return None

    def _enter_position(self, stock_code: str, current_price: float, quote: dict) -> Optional[Order]:
        """
        진입 (매수)

        Args:
            stock_code: 종목 코드
            current_price: 현재가
            quote: 현재가 정보

        Returns:
            생성된 Order
        """
        # 거래량 계산 (임시: 고정 수량)
        # 실제로는 리스크 관리에서 결정해야 함
        quantity = 10  # TODO: PositionSizer에서 계산

        # 매수 주문 생성
        order = self.executor.buy_order(stock_code, quantity, int(current_price))

        if order.status in [OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.FILLED]:
            # 거래 시작
            self.current_trade = Trade(
                stock_code=stock_code,
                entry_price=current_price,
                entry_time=quote.get("timestamp", datetime.now()),
                entry_order=order,
                quantity=quantity,
                stop_loss_price=current_price * 0.95,  # 5% 손절
                take_profit_price=current_price * 1.10,  # 10% 익절
            )

            self.state = TradeState.LONG
            log.info(
                f"[TRADE] Entered LONG for {stock_code} "
                f"@ {current_price} x {quantity} (Total: {current_price * quantity:,}원)"
            )
            return order
        else:
            log.error(f"Failed to create buy order for {stock_code}")
            return None

    def _exit_position(self, current_price: float) -> Optional[Order]:
        """
        청산 (매도)

        Args:
            current_price: 현재가

        Returns:
            생성된 Order
        """
        if self.current_trade is None:
            return None

        # 매도 주문
        order = self.executor.sell_order(
            self.current_trade.stock_code,
            self.current_trade.quantity,
            int(current_price),
        )

        if order.status in [OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.FILLED]:
            # 거래 완료
            self.current_trade.exit_price = current_price
            self.current_trade.exit_time = datetime.now()
            self.current_trade.exit_order = order

            pnl = self.current_trade.realized_pnl
            pnl_pct = self.current_trade.realized_pnl_pct

            log.info(
                f"[TRADE] Exited LONG for {self.current_trade.stock_code} "
                f"@ {current_price} | P&L: {pnl:+,.0f} ({pnl_pct:+.2f}%)"
            )

            self.completed_trades.append(self.current_trade)
            self.current_trade = None
            self.state = TradeState.IDLE
            return order
        else:
            log.error(f"Failed to create sell order for {self.current_trade.stock_code}")
            return None

    def _check_stop_loss_take_profit(self, current_price: float):
        """
        손절/익절 자동 체크

        Args:
            current_price: 현재가
        """
        if self.current_trade is None:
            return

        # 손절
        if (
            self.current_trade.stop_loss_price
            and current_price <= self.current_trade.stop_loss_price
        ):
            log.warning(
                f"[TRADE] Stop Loss triggered for {self.current_trade.stock_code} "
                f"@ {current_price}"
            )
            self._exit_position(current_price)

        # 익절
        elif (
            self.current_trade.take_profit_price
            and current_price >= self.current_trade.take_profit_price
        ):
            log.info(
                f"[TRADE] Take Profit triggered for {self.current_trade.stock_code} "
                f"@ {current_price}"
            )
            self._exit_position(current_price)

    def get_current_position(self) -> Optional[Trade]:
        """현재 포지션 조회"""
        return self.current_trade

    def get_trade_history(self) -> list:
        """완료된 거래 이력 조회"""
        return self.completed_trades

    def get_daily_pnl(self) -> float:
        """일일 손익"""
        pnl = sum(t.realized_pnl for t in self.completed_trades)
        if self.current_trade:
            pnl += self.current_trade.unrealized_pnl
        return pnl

    def get_win_rate(self) -> float:
        """승률 계산"""
        if not self.completed_trades:
            return 0.0
        wins = sum(1 for t in self.completed_trades if t.realized_pnl > 0)
        return (wins / len(self.completed_trades)) * 100


# 글로벌 거래 관리자 인스턴스
trade_manager = TradeManager()
