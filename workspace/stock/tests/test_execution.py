import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from stock.execution.order import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    OrderExecutor,
)
from stock.execution.trade_manager import Trade, TradeManager, TradeState
from stock.strategy.base import Signal


def test_order_creation():
    order = Order(
        order_id="TEST001",
        stock_code="005930",
        side=OrderSide.BUY,
        quantity=10,
        price=70000,
    )

    assert order.stock_code == "005930"
    assert order.side == OrderSide.BUY
    assert order.quantity == 10
    assert order.status == OrderStatus.PENDING


def test_trade_unrealized_pnl():
    trade = Trade(
        stock_code="005930",
        entry_price=70000,
        entry_time=datetime.now(),
        entry_order=MagicMock(),
        quantity=10,
    )

    trade.exit_price = 71000
    realized_pnl = trade.realized_pnl

    assert realized_pnl == 10000  # (71000 - 70000) * 10


def test_trade_realized_pnl_pct():
    trade = Trade(
        stock_code="005930",
        entry_price=70000,
        entry_time=datetime.now(),
        entry_order=MagicMock(),
        quantity=10,
    )

    trade.exit_price = 71000
    pnl_pct = trade.realized_pnl_pct

    # (71000 - 70000) / 70000 * 100 ≈ 1.43%
    assert abs(pnl_pct - 1.4286) < 0.01


def test_trade_manager_state_transition():
    manager = TradeManager()

    assert manager.state == TradeState.IDLE

    # 진입 신호
    quote = {
        "current_price": 70000,
        "timestamp": datetime.now(),
        "change_rate": 0.0,
        "volume": 1000000,
    }

    order = manager._enter_position("005930", 70000, quote)

    if order:
        assert manager.state == TradeState.LONG
        assert manager.current_trade is not None
        assert manager.current_trade.stock_code == "005930"


def test_trade_manager_daily_pnl():
    manager = TradeManager()

    # 테스트 거래
    entry_order = MagicMock()
    trade1 = Trade(
        stock_code="005930",
        entry_price=70000,
        entry_time=datetime.now(),
        entry_order=entry_order,
        quantity=10,
    )
    trade1.exit_price = 71000

    trade2 = Trade(
        stock_code="066570",
        entry_price=80000,
        entry_time=datetime.now(),
        entry_order=entry_order,
        quantity=5,
    )
    trade2.exit_price = 79000

    manager.completed_trades = [trade1, trade2]

    daily_pnl = manager.get_daily_pnl()

    # trade1: (71000 - 70000) * 10 = 10000
    # trade2: (79000 - 80000) * 5 = -5000
    # total: 5000
    assert daily_pnl == 5000


def test_trade_manager_win_rate():
    manager = TradeManager()

    entry_order = MagicMock()

    # 수익 거래
    trade1 = Trade(
        stock_code="005930",
        entry_price=70000,
        entry_time=datetime.now(),
        entry_order=entry_order,
        quantity=10,
    )
    trade1.exit_price = 71000

    # 손실 거래
    trade2 = Trade(
        stock_code="066570",
        entry_price=80000,
        entry_time=datetime.now(),
        entry_order=entry_order,
        quantity=5,
    )
    trade2.exit_price = 79000

    manager.completed_trades = [trade1, trade2]

    win_rate = manager.get_win_rate()

    # 1/2 = 50%
    assert win_rate == 50.0
