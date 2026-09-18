from typing import Optional
from datetime import datetime

from config.settings import settings
from stock.logging import log


class TelegramNotifier:
    """
    텔레그램 알림

    거래 이벤트, 에러, 일일 리포트를 텔레그램으로 전송
    """

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = settings.send_notifications and bool(self.bot_token) and bool(self.chat_id)

        if self.enabled:
            try:
                from telegram import Bot

                self.bot = Bot(token=self.bot_token)
            except ImportError:
                log.warning("python-telegram-bot not installed, notifications disabled")
                self.enabled = False
            except Exception as e:
                log.error(f"Failed to initialize Telegram bot: {e}")
                self.enabled = False
        else:
            self.bot = None

    def send_message(self, message: str) -> bool:
        """
        메시지 전송

        Args:
            message: 메시지 내용

        Returns:
            성공 여부
        """
        if not self.enabled:
            return False

        try:
            self.bot.send_message(chat_id=self.chat_id, text=message)
            return True
        except Exception as e:
            log.error(f"Failed to send Telegram message: {e}")
            return False

    def send_order_notification(
        self, side: str, stock_code: str, quantity: int, price: int
    ) -> bool:
        """주문 알림"""
        message = (
            f"📊 주문 실행\n"
            f"{'🔴 매도' if side == 'SELL' else '🟢 매수'}: {stock_code}\n"
            f"수량: {quantity}\n"
            f"가격: {price:,}원\n"
            f"금액: {quantity * price:,}원\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}"
        )

        return self.send_message(message)

    def send_fill_notification(
        self, side: str, stock_code: str, quantity: int, price: int
    ) -> bool:
        """체결 알림"""
        message = (
            f"✅ 체결\n"
            f"{'🔴 매도' if side == 'SELL' else '🟢 매수'}: {stock_code}\n"
            f"수량: {quantity}\n"
            f"가격: {price:,}원\n"
            f"금액: {quantity * price:,}원\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}"
        )

        return self.send_message(message)

    def send_pnl_notification(
        self, stock_code: str, entry_price: float, exit_price: float, pnl: float, pnl_pct: float
    ) -> bool:
        """손익 알림"""
        emoji = "🟢" if pnl > 0 else "🔴"
        message = (
            f"{emoji} 포지션 종료\n"
            f"종목: {stock_code}\n"
            f"진입: {entry_price:,}원\n"
            f"청산: {exit_price:,}원\n"
            f"손익: {pnl:+,}원 ({pnl_pct:+.2f}%)\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}"
        )

        return self.send_message(message)

    def send_error_notification(self, title: str, message: str) -> bool:
        """에러 알림"""
        full_message = (
            f"⚠️ 에러: {title}\n"
            f"{message}\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}"
        )

        return self.send_message(full_message)

    def send_circuit_breaker_alert(self, current_pnl: float, limit: float) -> bool:
        """서킷브레이커 알림"""
        message = (
            f"🛑 서킷브레이커 발동!\n"
            f"일일 손실 한도 도달\n"
            f"현재 손익: {current_pnl:,.0f}원\n"
            f"한도: {limit:,.0f}원\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"거래가 중단되었습니다."
        )

        return self.send_message(message)

    def send_daily_report(
        self,
        date: str,
        total_trades: int,
        winning_trades: int,
        daily_pnl: float,
        daily_return_pct: float,
    ) -> bool:
        """일일 리포트"""
        emoji = "🟢" if daily_pnl > 0 else "🔴" if daily_pnl < 0 else "⚪"

        message = (
            f"{emoji} 일일 리포트 - {date}\n"
            f"거래 수: {total_trades}\n"
            f"수익 거래: {winning_trades} ({(winning_trades/total_trades*100 if total_trades > 0 else 0):.1f}%)\n"
            f"일일 손익: {daily_pnl:+,.0f}원\n"
            f"일일 수익률: {daily_return_pct:+.2f}%"
        )

        return self.send_message(message)

    def send_startup_notification(self, mode: str, strategy: str) -> bool:
        """시작 알림"""
        mode_str = "모의투자" if mode == "paper" else "실거래"
        message = (
            f"🚀 트레이딩 봇 시작\n"
            f"모드: {mode_str}\n"
            f"전략: {strategy}\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}"
        )

        return self.send_message(message)

    def send_shutdown_notification(self, daily_pnl: float) -> bool:
        """종료 알림"""
        emoji = "🟢" if daily_pnl > 0 else "🔴" if daily_pnl < 0 else "⚪"
        message = (
            f"{emoji} 트레이딩 봇 종료\n"
            f"일일 손익: {daily_pnl:+,.0f}원\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}"
        )

        return self.send_message(message)


# 글로벌 텔레그램 알림 인스턴스
telegram_notifier = TelegramNotifier()
