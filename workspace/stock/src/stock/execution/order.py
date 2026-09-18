from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests

from config.settings import settings
from stock.auth.kis_auth import kis_auth
from stock.logging import log


class OrderType(Enum):
    """주문 유형"""

    LIMIT = "00"  # 지정가
    MARKET = "01"  # 시장가
    BEST = "02"  # 최유리


class OrderSide(Enum):
    """매매 방향"""

    BUY = "BUY"  # 매수
    SELL = "SELL"  # 매도


class OrderStatus(Enum):
    """주문 상태"""

    PENDING = "pending"  # 대기
    SUBMITTED = "submitted"  # 제출됨
    ACCEPTED = "accepted"  # 승인됨
    PARTIALLY_FILLED = "partially_filled"  # 부분 체결
    FILLED = "filled"  # 전량 체결
    CANCELLED = "cancelled"  # 취소됨
    REJECTED = "rejected"  # 거부됨


@dataclass
class Order:
    """주문"""

    order_id: str  # 주문 번호
    stock_code: str  # 종목 코드
    side: OrderSide  # 매수/매도
    quantity: int  # 주문 수량
    price: int  # 주문 가격 (0이면 시장가)
    order_type: OrderType = OrderType.LIMIT
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    server_order_id: Optional[str] = None  # KIS에서 반환한 주문번호


class OrderExecutor:
    """
    주문 실행기

    KIS API를 통해 실제 매매 주문을 생성/관리
    """

    def __init__(self):
        self.base_url = settings.kis_base_url
        self.account_number = settings.kis_account_number
        self.is_paper_mode = settings.is_paper_mode

    def _get_headers(self) -> dict:
        """API 요청 헤더"""
        return kis_auth.get_headers()

    def buy_order(self, stock_code: str, quantity: int, price: int = 0) -> Order:
        """
        매수 주문

        Args:
            stock_code: 종목 코드
            quantity: 수량
            price: 가격 (0이면 시장가)

        Returns:
            Order 객체
        """
        order_type = OrderType.MARKET if price == 0 else OrderType.LIMIT
        return self.place_order(stock_code, OrderSide.BUY, quantity, price, order_type)

    def sell_order(self, stock_code: str, quantity: int, price: int = 0) -> Order:
        """
        매도 주문

        Args:
            stock_code: 종목 코드
            quantity: 수량
            price: 가격 (0이면 시장가)

        Returns:
            Order 객체
        """
        order_type = OrderType.MARKET if price == 0 else OrderType.LIMIT
        return self.place_order(stock_code, OrderSide.SELL, quantity, price, order_type)

    def place_order(
        self, stock_code: str, side: OrderSide, quantity: int, price: int, order_type: OrderType
    ) -> Order:
        """
        주문 생성

        Args:
            stock_code: 종목 코드
            side: 매수/매도
            quantity: 수량
            price: 가격
            order_type: 주문 유형

        Returns:
            Order 객체
        """
        # 임시 주문 ID 생성 (실제는 KIS에서 받음)
        order_id = f"{stock_code}_{side.value}_{int(datetime.now().timestamp())}"

        order = Order(
            order_id=order_id,
            stock_code=stock_code,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

        try:
            # KIS API에 주문
            response = self._send_order_to_kis(order)

            if response.get("rt_cd") == "0":
                # 성공
                order.status = OrderStatus.SUBMITTED
                order.server_order_id = response.get("output", {}).get("ODNO", "")
                log.info(
                    f"[ORDER] {side.value} {quantity} shares of {stock_code} "
                    f"@ {price if price > 0 else 'MARKET'} | "
                    f"Order ID: {order.server_order_id}"
                )
            else:
                # 실패
                order.status = OrderStatus.REJECTED
                log.error(f"Order rejected: {response.get('msg1', 'Unknown error')}")

        except Exception as e:
            log.error(f"Failed to place order: {e}")
            order.status = OrderStatus.REJECTED

        return order

    def _send_order_to_kis(self, order: Order) -> dict:
        """
        KIS API로 주문 전송

        Args:
            order: Order 객체

        Returns:
            API 응답
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        headers = self._get_headers()

        # 주문 방향 매핑
        ord_dvsn = "01" if order.side == OrderSide.BUY else "02"

        body = {
            "CANO": self.account_number.split("-")[0],  # 계좌번호 앞 8자리
            "ACNT_PRDT_CD": self.account_number.split("-")[1],  # 계좌상품코드 뒤 2자리
            "PDNO": order.stock_code,
            "ORD_QTY": str(order.quantity),
            "ORD_UNPR": str(order.price) if order.price > 0 else "0",
            "ORD_DVSN": order.order_type.value,  # 00=지정가, 01=시장가
            "CMA_EVALU_AMT_ICLD_YN": "Y",
            "ORD_SVR_DVSN_CODE": "0",
            "CTAC_TLNO": "",
            "CTAC_TLNO2": "",
            "ORD_BTN": ord_dvsn,  # 01=매수, 02=매도
            "TgtStnCd": "",
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                verify=False,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            log.error(f"KIS API request failed: {e}")
            return {"rt_cd": "-1", "msg1": str(e)}

    def get_order_status(self, order_id: str) -> OrderStatus:
        """
        주문 상태 조회 (간단한 구현)

        실제로는 KIS API의 PSEARCH1 (주문조회) 엔드포인트 호출 필요
        """
        # 모의투자에서는 즉시 체결로 가정
        return OrderStatus.FILLED

    def cancel_order(self, order: Order) -> bool:
        """
        주문 취소

        Args:
            order: Order 객체

        Returns:
            성공 여부
        """
        if not order.server_order_id:
            log.error("Cannot cancel order without server_order_id")
            return False

        try:
            # KIS API에 취소 요청
            url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cancel"
            headers = self._get_headers()

            body = {
                "CANO": self.account_number.split("-")[0],
                "ACNT_PRDT_CD": self.account_number.split("-")[1],
                "ORGN_ODNO": order.server_order_id,
                "ORD_DVSN": "00",
                "CFRM_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            }

            response = requests.post(url, headers=headers, json=body, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("rt_cd") == "0":
                order.status = OrderStatus.CANCELLED
                log.info(f"Order {order.server_order_id} cancelled")
                return True
            else:
                log.error(f"Cancel request rejected: {data.get('msg1', 'Unknown error')}")
                return False

        except Exception as e:
            log.error(f"Failed to cancel order: {e}")
            return False

    def get_positions(self) -> dict:
        """
        현재 보유 포지션 조회

        Returns:
            종목코드별 수량 딕셔너리
        """
        try:
            url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-psearch1"
            headers = self._get_headers()

            params = {
                "CANO": self.account_number.split("-")[0],
                "ACNT_PRDT_CD": self.account_number.split("-")[1],
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "N",
                "INQR_DVSN": "00",
                "UNPR_DVSN": "01",
                "FUND_SELN_CHK": "0",
                "ACNT_LEDG_DVSN": "00",
                "Ädiv": "00000000",
                "SORT_SQN": "D",
                "QSIR_MDIA_DVSN": "0",
            }

            response = requests.get(
                url,
                headers=headers,
                params=params,
                verify=False,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            positions = {}
            for item in data.get("output1", []):
                stock_code = item.get("PDNO")
                quantity = int(item.get("HLDG_QTY", 0))
                if quantity > 0:
                    positions[stock_code] = quantity

            return positions

        except Exception as e:
            log.error(f"Failed to get positions: {e}")
            return {}


# 글로벌 주문 실행기 인스턴스
order_executor = OrderExecutor()
