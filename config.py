"""
Конфигурация бота
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: str = os.getenv("ADMIN_IDS", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./bot.db")
    
    @property
    def admin_ids_list(self) -> list:
        if not self.ADMIN_IDS:
            return []
        return [int(id.strip()) for id in self.ADMIN_IDS.split(",") if id.strip()]
    
    class Config:
        env_file = ".env"


settings = Settings()
