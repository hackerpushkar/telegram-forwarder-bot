import os
from typing import List, Any, Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class BotConfig(BaseSettings):
    BOT_TOKEN: str = ""
    ADMIN_IDS: Any = []
    
    # Userbot (MTProto) settings from my.telegram.org
    API_ID: int = 0
    API_HASH: str = ""
    SESSION_STRING: str = ""
    USERBOT_SESSION_NAME: str = "data/userbot"
    
    DB_PATH: str = "data/forwarder.db"
    ADMINS_ONLY: bool = True
    DEFAULT_FORWARD_MODE: str = "copy"  # "copy" or "forward"
    MAX_RETRIES: int = 5
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def normalize_admin_ids(cls, v) -> List[int]:
        if v is None:
            return []
        if isinstance(v, (int, float)):
            return [int(v)]
        if isinstance(v, str):
            v = v.strip().strip("[]'\"")
            if not v:
                return []
            ids = []
            for item in v.split(","):
                clean = item.strip().strip("'\"")
                if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
                    ids.append(int(clean))
            return ids
        if isinstance(v, (list, tuple, set)):
            result = []
            for x in v:
                if isinstance(x, (int, float)):
                    result.append(int(x))
                elif isinstance(x, str) and (x.strip().isdigit() or (x.strip().startswith("-") and x.strip()[1:].isdigit())):
                    result.append(int(x.strip()))
            return result
        return []

    @field_validator("API_ID", mode="before")
    @classmethod
    def parse_api_id(cls, v) -> int:
        if v is None or v == "":
            return 0
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
        return 0

    def is_admin(self, user_id: int) -> bool:
        if not self.ADMINS_ONLY:
            return True
        if not self.ADMIN_IDS:
            return True
        return user_id in self.ADMIN_IDS

def load_config() -> BotConfig:
    config = BotConfig()
    db_dir = Path(config.DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    return config

config = load_config()
