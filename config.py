"""
Конфигурация бота — все настройки из переменных окружения
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: str = os.getenv("ADMIN_IDS", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

    # Тарифы (руб.)
    PRICE_BASIC: int = 299
    PRICE_PRO: int = 799
    PRICE_BUSINESS: int = 1999

    # Реквизиты для оплаты (СБП / карта)
    PAYMENT_CARD: str = os.getenv("PAYMENT_CARD", "2200 0000 0000 0000")
    PAYMENT_PHONE: str = os.getenv("PAYMENT_PHONE", "+7 900 000-00-00")

    # Реферальный бонус (дней подписки)
    REFERRAL_BONUS_DAYS: int = 7

    @property
    def admin_ids_list(self) -> list[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit()]

    class Config:
        env_file = ".env"


settings = Settings()
