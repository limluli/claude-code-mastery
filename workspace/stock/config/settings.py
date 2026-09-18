from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # KIS API - Paper Trading
    kis_app_key_paper: str
    kis_app_secret_paper: str
    kis_account_number_paper: str

    # KIS API - Live Trading
    kis_app_key_live: str
    kis_app_secret_live: str
    kis_account_number_live: str

    # Trading Mode
    trading_mode: str = "paper"  # paper or live

    # Strategy Settings
    strategy_type: str = "ma_cross"
    ma_short_period: int = 5
    ma_long_period: int = 20

    # Risk Management
    max_position_ratio: float = 0.05
    daily_loss_limit: float = -50000.0
    stop_loss_ratio: float = 0.05
    take_profit_ratio: float = 0.10

    # Notification
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    send_notifications: bool = False

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/trading.log"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def is_paper_mode(self) -> bool:
        return self.trading_mode == "paper"

    @property
    def kis_app_key(self) -> str:
        return self.kis_app_key_paper if self.is_paper_mode else self.kis_app_key_live

    @property
    def kis_app_secret(self) -> str:
        return self.kis_app_secret_paper if self.is_paper_mode else self.kis_app_secret_live

    @property
    def kis_account_number(self) -> str:
        return self.kis_account_number_paper if self.is_paper_mode else self.kis_account_number_live

    @property
    def kis_base_url(self) -> str:
        if self.is_paper_mode:
            return "https://openapivts.koreainvestment.com:29443"
        else:
            return "https://openapi.koreainvestment.com:9443"


# 글로벌 설정 인스턴스
settings = Settings()
