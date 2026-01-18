"""
設定ファイル
環境変数から読み込み
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LINE Bot
    LINE_CHANNEL_SECRET: str = ""
    LINE_CHANNEL_ACCESS_TOKEN: str = ""

    # KIE.AI
    KIEAI_API_KEY: str = ""

    # Database (Google Sheets or SQLite)
    DATABASE_URL: str = "sqlite:///./users.db"

    # Google Sheets（オプション）
    GOOGLE_SHEETS_CREDENTIALS: str = ""
    GOOGLE_SHEETS_ID: str = ""

    # 無料枠
    FREE_MONTHLY_LIMIT: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
