import asyncio
import json
import time
from typing import Callable, Optional
from datetime import datetime

import websockets

from config.settings import settings
from stock.auth.kis_auth import kis_auth
from stock.logging import log


class KISWebSocketClient:
    def __init__(self):
        self.base_url = settings.kis_base_url.replace("https", "wss")
        self.ws = None
        self.is_connected = False
        self.subscribed_stocks = set()
        self.on_price_update: Optional[Callable] = None
        self.reconnect_attempt = 0
        self.max_reconnect_attempts = 5

    async def connect(self):
        """WebSocket 연결"""
        try:
            ws_url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/realtime"
            log.info(f"Connecting to KIS WebSocket: {ws_url}")

            self.ws = await websockets.connect(ws_url, ping_interval=60, ping_timeout=10)
            self.is_connected = True
            self.reconnect_attempt = 0

            # 연결 후 승인 필요
            await self._send_approval_request()

            log.info("✓ WebSocket connected")

        except Exception as e:
            log.error(f"Failed to connect WebSocket: {e}")
            self.is_connected = False
            await self._attempt_reconnect()

    async def _send_approval_request(self):
        """WebSocket 사용 승인 요청"""
        token = kis_auth.get_access_token()
        approval_msg = {
            "header": {
                "approval_key": token,  # 실제로는 별도의 approval_key가 필요하지만, 테스트용으로 token 사용
                "custtype": "P",  # P=개인
                "tr_type": "1",  # 1=실시간
                "content-type": "utf-8",
            }
        }
        try:
            await self.ws.send(json.dumps(approval_msg))
            log.debug("Sent approval request to WebSocket")
        except Exception as e:
            log.error(f"Failed to send approval request: {e}")

    async def subscribe(self, stock_code: str):
        """
        특정 종목의 실시간 시세 구독

        Args:
            stock_code: 종목코드 (예: '005930' = 삼성전자)
        """
        if not self.is_connected:
            log.warning(f"WebSocket not connected, cannot subscribe {stock_code}")
            return

        if stock_code in self.subscribed_stocks:
            log.debug(f"Already subscribed to {stock_code}")
            return

        subscribe_msg = {
            "header": {
                "tr_id": "H0STCNT0",  # 국내주식현재가 실시간
                "tr_key": stock_code,
                "content-type": "utf-8",
            }
        }

        try:
            await self.ws.send(json.dumps(subscribe_msg))
            self.subscribed_stocks.add(stock_code)
            log.info(f"✓ Subscribed to {stock_code}")
        except Exception as e:
            log.error(f"Failed to subscribe to {stock_code}: {e}")

    async def unsubscribe(self, stock_code: str):
        """특정 종목의 실시간 시세 구독 해제"""
        if not self.is_connected:
            return

        unsubscribe_msg = {
            "header": {
                "tr_id": "H0STCNT0",
                "tr_key": stock_code,
                "content-type": "utf-8",
            },
            "body": {"gubun": "1"},  # 1=구독해제
        }

        try:
            await self.ws.send(json.dumps(unsubscribe_msg))
            self.subscribed_stocks.discard(stock_code)
            log.info(f"Unsubscribed from {stock_code}")
        except Exception as e:
            log.error(f"Failed to unsubscribe from {stock_code}: {e}")

    async def listen(self):
        """WebSocket 메시지 수신 및 처리 루프"""
        while True:
            if not self.is_connected:
                await self._attempt_reconnect()
                await asyncio.sleep(5)
                continue

            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=120)
                data = json.loads(msg)

                if data.get("header", {}).get("tr_id") == "H0STCNT0":
                    # 실시간 시세 업데이트
                    await self._handle_price_update(data)
                elif "APPROV" in msg:
                    log.info("✓ WebSocket approval confirmed")

            except asyncio.TimeoutError:
                log.warning("WebSocket receive timeout, attempting to reconnect...")
                await self._attempt_reconnect()
            except Exception as e:
                log.error(f"Error in WebSocket listen loop: {e}")
                await self._attempt_reconnect()

    async def _handle_price_update(self, data: dict):
        """실시간 시세 데이터 처리"""
        try:
            body = data.get("body", {})
            stock_code = body.get("stck_code", "")
            current_price = int(body.get("stck_prpr", 0))
            change_rate = float(body.get("prdy_ctrt", 0.0))
            volume = int(body.get("cntg_vol", 0))

            price_data = {
                "stock_code": stock_code,
                "current_price": current_price,
                "change_rate": change_rate,
                "volume": volume,
                "timestamp": datetime.now(),
            }

            log.debug(f"[{stock_code}] {current_price} ({change_rate:+.2f}%) vol:{volume}")

            # 콜백 함수 호출
            if self.on_price_update:
                self.on_price_update(price_data)

        except Exception as e:
            log.error(f"Error handling price update: {e}")

    async def _attempt_reconnect(self):
        """WebSocket 재연결 시도"""
        if self.reconnect_attempt >= self.max_reconnect_attempts:
            log.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) exceeded")
            self.is_connected = False
            return

        self.reconnect_attempt += 1
        wait_time = 2 ** self.reconnect_attempt  # Exponential backoff
        log.info(f"Attempting to reconnect (attempt {self.reconnect_attempt}/{self.max_reconnect_attempts}) in {wait_time}s...")
        await asyncio.sleep(wait_time)

        try:
            await self.connect()
            # 재구독
            for stock_code in self.subscribed_stocks.copy():
                await self.subscribe(stock_code)
        except Exception as e:
            log.error(f"Reconnection failed: {e}")

    async def close(self):
        """WebSocket 연결 종료"""
        if self.ws:
            await self.ws.close()
        self.is_connected = False
        log.info("WebSocket closed")


# 글로벌 WebSocket 클라이언트 인스턴스
kis_ws = KISWebSocketClient()


async def run_websocket_example():
    """WebSocket 사용 예제"""
    from stock.market_data.ws_client import kis_ws

    def on_price_update(data):
        print(f"Price update: {data}")

    kis_ws.on_price_update = on_price_update

    try:
        await kis_ws.connect()

        # 삼성전자, LG전자 구독
        await kis_ws.subscribe("005930")
        await kis_ws.subscribe("066570")

        # 10초 수신
        await asyncio.sleep(10)

    finally:
        await kis_ws.close()


if __name__ == "__main__":
    asyncio.run(run_websocket_example())
