from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    BOT_TOKEN: str
    PAYMENT_TOKEN: str
    ADMIN_IDS: str
    DATABASE_URL: str = "sqlite:///bot.db"
    WEBHOOK_HOST: str = "https://your-domain.com"
    WEBHOOK_PATH: str = "/webhook/bot"
    DEBUG: bool = True
    
    @property
    def admin_ids_list(self) -> List[int]:
        return [int(id.strip()) for id in self.ADMIN_IDS.split(",") if id.strip()]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
