import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from stock.market_data.rest_client import KISRestClient
from stock.market_data.data_manager import DataManager


@patch("stock.market_data.rest_client.requests.get")
@patch("stock.market_data.rest_client.kis_auth.get_headers")
def test_get_daily_ohlcv(mock_headers, mock_get):
    mock_headers.return_value = {"Authorization": "Bearer test"}

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "rt_cd": "0",
        "output": [
            {
                "stck_bsop_date": "20240101",
                "stck_oprc": "70000",
                "stck_hgpr": "71000",
                "stck_lwpr": "69000",
                "stck_clpr": "70500",
                "acml_vol": "1000000",
            },
            {
                "stck_bsop_date": "20240102",
                "stck_oprc": "70500",
                "stck_hgpr": "71500",
                "stck_lwpr": "70000",
                "stck_clpr": "71000",
                "acml_vol": "1500000",
            },
        ],
    }
    mock_get.return_value = mock_response

    client = KISRestClient()
    df = client.get_daily_ohlcv("005930")

    assert len(df) == 2
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert df.iloc[0]["close"] == 70500
    assert df.iloc[1]["close"] == 71000


@patch("stock.market_data.rest_client.requests.get")
@patch("stock.market_data.rest_client.kis_auth.get_headers")
def test_get_quote(mock_headers, mock_get):
    mock_headers.return_value = {"Authorization": "Bearer test"}

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "rt_cd": "0",
        "output": {
            "stck_prpr": "70500",
            "stck_hgpr": "71000",
            "stck_lwpr": "69000",
            "stck_prdy_clpr": "70000",
            "acml_vol": "1000000",
            "prdy_ctrt": "0.71",
        },
    }
    mock_get.return_value = mock_response

    client = KISRestClient()
    quote = client.get_quote("005930")

    assert quote["stock_code"] == "005930"
    assert quote["current_price"] == 70500
    assert quote["change_rate"] == 0.71


def test_data_manager_save_and_load(tmp_path):
    manager = DataManager(str(tmp_path))

    # 테스트 데이터
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "open": [70000 + i * 100 for i in range(10)],
            "high": [71000 + i * 100 for i in range(10)],
            "low": [69000 + i * 100 for i in range(10)],
            "close": [70500 + i * 100 for i in range(10)],
            "volume": [1000000 + i * 100000 for i in range(10)],
        }
    )

    # 저장
    manager.save_daily_ohlcv("005930", df)

    # 로드
    loaded_df = manager.load_daily_ohlcv("005930")

    assert len(loaded_df) == 10
    assert loaded_df.iloc[0]["close"] == 70500
    assert loaded_df.iloc[-1]["close"] == 70900


def test_data_manager_append_mode(tmp_path):
    manager = DataManager(str(tmp_path))

    # 첫 번째 저장
    df1 = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "open": [70000 + i * 100 for i in range(5)],
            "high": [71000 + i * 100 for i in range(5)],
            "low": [69000 + i * 100 for i in range(5)],
            "close": [70500 + i * 100 for i in range(5)],
            "volume": [1000000 + i * 100000 for i in range(5)],
        }
    )
    manager.save_daily_ohlcv("005930", df1)

    # 두 번째 저장 (append)
    df2 = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-06", periods=5, freq="D"),
            "open": [70500 + i * 100 for i in range(5)],
            "high": [71500 + i * 100 for i in range(5)],
            "low": [70000 + i * 100 for i in range(5)],
            "close": [71000 + i * 100 for i in range(5)],
            "volume": [1500000 + i * 100000 for i in range(5)],
        }
    )
    manager.save_daily_ohlcv("005930", df2, mode="append")

    # 로드
    loaded_df = manager.load_daily_ohlcv("005930")

    # 10개 모두 있어야 함
    assert len(loaded_df) == 10
