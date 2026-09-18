import pytest
from unittest.mock import patch, MagicMock
from stock.auth.kis_auth import KISAuth


@patch("stock.auth.kis_auth.requests.post")
def test_kis_auth_get_token_success(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "test_token_123",
        "expires_in": 3600,
    }
    mock_post.return_value = mock_response

    auth = KISAuth()
    token = auth.get_access_token()

    assert token == "test_token_123"
    assert auth.access_token == "test_token_123"
    mock_post.assert_called_once()


@patch("stock.auth.kis_auth.requests.post")
def test_kis_auth_uses_cached_token(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "test_token_123",
        "expires_in": 3600,
    }
    mock_post.return_value = mock_response

    auth = KISAuth()
    token1 = auth.get_access_token()
    token2 = auth.get_access_token()

    assert token1 == token2
    assert mock_post.call_count == 1  # Only called once due to caching


def test_kis_auth_get_headers():
    auth = KISAuth()
    auth.access_token = "test_token_123"
    headers = auth.get_headers()

    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer test_token_123"
    assert "Content-Type" in headers
