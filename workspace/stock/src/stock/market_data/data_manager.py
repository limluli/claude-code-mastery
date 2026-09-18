from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

from stock.logging import log


class DataManager:
    def __init__(self, data_dir: str = "data"):
        self.raw_dir = Path(data_dir) / "raw"
        self.processed_dir = Path(data_dir) / "processed"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def save_daily_ohlcv(self, stock_code: str, df: pd.DataFrame, mode: str = "append"):
        """
        일봉 OHLCV를 Parquet 형식으로 저장

        Args:
            stock_code: 종목코드
            df: OHLCV 데이터프레임
            mode: 저장 방식 ('overwrite' 또는 'append')
        """
        if df.empty:
            log.warning(f"Empty dataframe for {stock_code}, skipping save")
            return

        file_path = self.raw_dir / f"{stock_code}_daily.parquet"

        try:
            if mode == "append" and file_path.exists():
                existing_df = pd.read_parquet(file_path)
                # 중복 제거 (date 기준)
                df = pd.concat([existing_df, df]).drop_duplicates(subset=["date"], keep="last")

            df = df.sort_values("date").reset_index(drop=True)
            df.to_parquet(file_path, compression="snappy", index=False)
            log.info(f"Saved {len(df)} daily bars for {stock_code} to {file_path}")

        except Exception as e:
            log.error(f"Failed to save daily OHLCV for {stock_code}: {e}")

    def load_daily_ohlcv(self, stock_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        저장된 일봉 OHLCV 로드

        Args:
            stock_code: 종목코드
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)

        Returns:
            필터링된 OHLCV 데이터프레임
        """
        file_path = self.raw_dir / f"{stock_code}_daily.parquet"

        if not file_path.exists():
            log.warning(f"No daily data found for {stock_code}")
            return pd.DataFrame()

        try:
            df = pd.read_parquet(file_path)

            if start_date:
                start = pd.to_datetime(start_date)
                df = df[df["date"] >= start]

            if end_date:
                end = pd.to_datetime(end_date)
                df = df[df["date"] <= end]

            log.info(f"Loaded {len(df)} daily bars for {stock_code} ({start_date} ~ {end_date})")
            return df

        except Exception as e:
            log.error(f"Failed to load daily OHLCV for {stock_code}: {e}")
            return pd.DataFrame()

    def save_minute_ohlcv(self, stock_code: str, df: pd.DataFrame, timeframe: int = 1, mode: str = "append"):
        """
        분봉 OHLCV를 Parquet 형식으로 저장

        Args:
            stock_code: 종목코드
            df: 분봉 데이터프레임
            timeframe: 봉 단위 (1=1분, 5=5분 등)
            mode: 저장 방식
        """
        if df.empty:
            log.warning(f"Empty dataframe for {stock_code} {timeframe}min, skipping save")
            return

        file_path = self.raw_dir / f"{stock_code}_{timeframe}min.parquet"

        try:
            if mode == "append" and file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df]).drop_duplicates(subset=["timestamp"], keep="last")

            df = df.sort_values("timestamp").reset_index(drop=True)
            df.to_parquet(file_path, compression="snappy", index=False)
            log.info(f"Saved {len(df)} {timeframe}min bars for {stock_code} to {file_path}")

        except Exception as e:
            log.error(f"Failed to save minute OHLCV for {stock_code}: {e}")

    def load_minute_ohlcv(self, stock_code: str, timeframe: int = 1, days: int = 1) -> pd.DataFrame:
        """
        저장된 분봉 OHLCV 로드 (최근 N일)

        Args:
            stock_code: 종목코드
            timeframe: 봉 단위
            days: 최근 몇 일치 데이터

        Returns:
            분봉 데이터프레임
        """
        file_path = self.raw_dir / f"{stock_code}_{timeframe}min.parquet"

        if not file_path.exists():
            log.warning(f"No {timeframe}min data found for {stock_code}")
            return pd.DataFrame()

        try:
            df = pd.read_parquet(file_path)
            cutoff_time = datetime.now() - timedelta(days=days)
            df = df[df["timestamp"] >= cutoff_time]

            log.info(f"Loaded {len(df)} {timeframe}min bars for {stock_code} (last {days}d)")
            return df

        except Exception as e:
            log.error(f"Failed to load minute OHLCV for {stock_code}: {e}")
            return pd.DataFrame()

    def save_quote(self, stock_code: str, quote: dict):
        """
        현재가 정보를 CSV로 저장 (로그용)

        Args:
            stock_code: 종목코드
            quote: 현재가 딕셔너리
        """
        csv_path = self.processed_dir / "quotes.csv"

        try:
            quote_df = pd.DataFrame([quote])

            if csv_path.exists():
                existing_df = pd.read_csv(csv_path)
                quote_df = pd.concat([existing_df, quote_df], ignore_index=True)

            quote_df.to_csv(csv_path, index=False)
            log.debug(f"Saved quote for {stock_code}")

        except Exception as e:
            log.error(f"Failed to save quote for {stock_code}: {e}")

    def get_available_stocks(self) -> list:
        """저장된 모든 종목 조회"""
        try:
            daily_files = list(self.raw_dir.glob("*_daily.parquet"))
            stocks = [f.stem.replace("_daily", "") for f in daily_files]
            return sorted(stocks)
        except Exception as e:
            log.error(f"Failed to get available stocks: {e}")
            return []


# 글로벌 데이터 관리자 인스턴스
data_manager = DataManager()
