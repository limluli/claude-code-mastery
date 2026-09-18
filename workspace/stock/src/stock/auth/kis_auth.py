import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from config.settings import settings
from stock.logging import log


class KISAuth:
    def __init__(self):
        self.base_url = settings.kis_base_url
        self.app_key = settings.kis_app_key
        self.app_secret = settings.kis_app_secret
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.token_cache_file = Path("cache/kis_token.json")

    def get_access_token(self) -> str:
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at - timedelta(minutes=5):
            log.debug("Using cached access token")
            return self.access_token

        if self.token_cache_file.exists():
            try:
                cached = json.loads(self.token_cache_file.read_text())
                expires_at = datetime.fromisoformat(cached["expires_at"])
                if datetime.now() < expires_at - timedelta(minutes=5):
                    self.access_token = cached["token"]
                    self.token_expires_at = expires_at
                    log.info("Loaded access token from cache")
                    return self.access_token
            except Exception as e:
                log.warning(f"Failed to load cached token: {e}")

        log.info("Requesting new access token from KIS API")
        self._request_new_token()
        return self.access_token

    def _request_new_token(self):
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"Content-Type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        try:
            response = requests.post(url, headers=headers, json=body, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()

            self.access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            self._cache_token()
            log.info(f"New access token obtained (expires in {expires_in}s)")

        except requests.RequestException as e:
            log.error(f"Failed to request access token: {e}")
            raise

    def _cache_token(self):
        self.token_cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "token": self.access_token,
            "expires_at": self.token_expires_at.isoformat(),
        }
        self.token_cache_file.write_text(json.dumps(cache_data, indent=2))

    def get_headers(self) -> dict:
        token = self.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
        }


# 글로벌 인증 인스턴스
kis_auth = KISAuth()


if __name__ == "__main__":
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        token = kis_auth.get_access_token()
        log.info("✓ Access token obtained successfully")
        log.info(f"Token: {token[:20]}...")
    except Exception as e:
        log.error(f"✗ Failed to obtain access token: {e}")
