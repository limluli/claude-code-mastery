from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import requests

from config.settings import settings
from stock.auth.kis_auth import kis_auth
from stock.logging import log


class KISRestClient:
    def __init__(self):
        self.base_url = settings.kis_base_url
        self.account_number = settings.kis_account_number

    def get_daily_ohlcv(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: int = 100,
    ) -> pd.DataFrame:
        """
        일봉(Daily OHLCV) 데이터 조회

        Args:
            stock_code: 종목코드 (예: '005930' = 삼성전자)
            start_date: 시작일 (YYYYMMDD 형식, None이면 count개 최근 데이터)
            end_date: 종료일 (YYYYMMDD 형식)
            count: 조회 건수 (최대 100)

        Returns:
            OHLCV 데이터프레임 (Date, Open, High, Low, Close, Volume)
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        headers = kis_auth.get_headers()

        params = {
            "fid_cond_mrkt_div_code": "J",  # J=전체
            "fid_input_iscd": stock_code,
            "fid_input_date_1": end_date or datetime.now().strftime("%Y%m%d"),
            "fid_input_date_2": start_date or "19000101",
            "fid_period_div_code": "D",  # D=일봉
            "fid_org_adj_prc": "1",  # 1=수정주가
            "fid_adj_prc_div": "0",
        }

        try:
            response = requests.get(url, headers=headers, params=params, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("rt_cd") != "0":
                log.error(f"KIS API error: {data.get('msg1', 'Unknown error')}")
                return pd.DataFrame()

            items = data.get("output", [])[:count]
            if not items:
                log.warning(f"No data found for {stock_code}")
                return pd.DataFrame()

            df = pd.DataFrame(
                [
                    {
                        "date": datetime.strptime(item["stck_bsop_date"], "%Y%m%d"),
                        "open": int(item["stck_oprc"]),
                        "high": int(item["stck_hgpr"]),
                        "low": int(item["stck_lwpr"]),
                        "close": int(item["stck_clpr"]),
                        "volume": int(item["acml_vol"]),
                    }
                    for item in items
                ]
            )

            df = df.sort_values("date").reset_index(drop=True)
            log.info(f"Retrieved {len(df)} daily bars for {stock_code} ({df['date'].min()} ~ {df['date'].max()})")
            return df

        except requests.RequestException as e:
            log.error(f"Failed to fetch daily OHLCV for {stock_code}: {e}")
            return pd.DataFrame()

    def get_minute_ohlcv(
        self,
        stock_code: str,
        timeframe: int = 1,
        count: int = 100,
    ) -> pd.DataFrame:
        """
        분봉(Minute OHLCV) 데이터 조회

        Args:
            stock_code: 종목코드
            timeframe: 봉의 시간 단위 (1=1분, 5=5분, 10=10분, 15=15분, 30=30분, 60=60분)
            count: 조회 건수 (최대 100)

        Returns:
            분봉 OHLCV 데이터프레임
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        headers = kis_auth.get_headers()

        # timeframe 매핑
        timeframe_map = {1: "1", 5: "5", 10: "10", 15: "15", 30: "30", 60: "60"}
        period_div_code = timeframe_map.get(timeframe, "1")

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
            "fid_input_hour_1": datetime.now().strftime("%H%M%S"),
            "fid_pw_data_incu_yn": "Y",
            "fid_period_div_code": period_div_code,
            "fid_org_adj_prc": "1",
        }

        try:
            response = requests.get(url, headers=headers, params=params, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("rt_cd") != "0":
                log.error(f"KIS API error: {data.get('msg1', 'Unknown error')}")
                return pd.DataFrame()

            items = data.get("output", [])[:count]
            if not items:
                log.warning(f"No minute data found for {stock_code}")
                return pd.DataFrame()

            df = pd.DataFrame(
                [
                    {
                        "timestamp": datetime.strptime(
                            f"{item['stck_bsop_date']} {item['stck_cntg_hour']}",
                            "%Y%m%d %H%M%S",
                        ),
                        "open": int(item["stck_oprc"]),
                        "high": int(item["stck_hgpr"]),
                        "low": int(item["stck_lwpr"]),
                        "close": int(item["stck_clpr"]),
                        "volume": int(item["cntg_vol"]),
                    }
                    for item in items
                ]
            )

            df = df.sort_values("timestamp").reset_index(drop=True)
            log.info(f"Retrieved {len(df)} {timeframe}min bars for {stock_code}")
            return df

        except requests.RequestException as e:
            log.error(f"Failed to fetch minute OHLCV for {stock_code}: {e}")
            return pd.DataFrame()

    def get_quote(self, stock_code: str) -> dict:
        """
        현재 시세 조회 (주가, 거래량, 등락률 등)

        Args:
            stock_code: 종목코드

        Returns:
            현재가 정보 딕셔너리
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = kis_auth.get_headers()

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
        }

        try:
            response = requests.get(url, headers=headers, params=params, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("rt_cd") != "0":
                log.error(f"KIS API error: {data.get('msg1', 'Unknown error')}")
                return {}

            output = data.get("output", {})
            quote = {
                "stock_code": stock_code,
                "current_price": int(output.get("stck_prpr", 0)),
                "high_price": int(output.get("stck_hgpr", 0)),
                "low_price": int(output.get("stck_lwpr", 0)),
                "prev_close": int(output.get("stck_prdy_clpr", 0)),
                "volume": int(output.get("acml_vol", 0)),
                "change_rate": float(output.get("prdy_ctrt", 0.0)),
                "timestamp": datetime.now(),
            }
            log.debug(f"Quote {stock_code}: {quote['current_price']}원 ({quote['change_rate']:+.2f}%)")
            return quote

        except requests.RequestException as e:
            log.error(f"Failed to fetch quote for {stock_code}: {e}")
            return {}


# 글로벌 REST 클라이언트 인스턴스
kis_rest = KISRestClient()
