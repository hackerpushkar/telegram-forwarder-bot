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
    MONGO_URI: Optional[str] = None
    MONGO_DB_NAME: str = "forwarder_bot"
    ADMINS_ONLY: bool = True
    DEFAULT_FORWARD_MODE: str = "copy"  # "copy" or "forward"
    MAX_RETRIES: int = 5
    
    # Force Subscribe Channels (Limit: 1 to 12 channels)
    FORCE_SUB_CHANNELS: Any = []
    FORCE_SUB_1: Optional[str] = None
    FORCE_SUB_2: Optional[str] = None
    FORCE_SUB_3: Optional[str] = None
    FORCE_SUB_4: Optional[str] = None
    FORCE_SUB_5: Optional[str] = None
    FORCE_SUB_6: Optional[str] = None
    FORCE_SUB_7: Optional[str] = None
    FORCE_SUB_8: Optional[str] = None
    FORCE_SUB_9: Optional[str] = None
    FORCE_SUB_10: Optional[str] = None
    FORCE_SUB_11: Optional[str] = None
    FORCE_SUB_12: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("FORCE_SUB_CHANNELS", mode="before")
    @classmethod
    def normalize_force_sub_channels(cls, v) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            v = v.strip().strip("[]'\"")
            if not v:
                return []
            channels = []
            for item in v.split(","):
                clean = item.strip().strip("'\"")
                if clean:
                    channels.append(clean)
            return channels[:12]
        if isinstance(v, (list, tuple, set)):
            result = []
            for x in v:
                if isinstance(x, str) and x.strip():
                    result.append(x.strip().strip("'\""))
                elif isinstance(x, int):
                    result.append(str(x))
            return result[:12]
        return []

    def get_configured_force_channels(self) -> List[str]:
        """Collect all force subscribe channels from FORCE_SUB_CHANNELS and FORCE_SUB_1..12 (max 12)."""
        channels: List[str] = []
        if isinstance(self.FORCE_SUB_CHANNELS, list):
            for ch in self.FORCE_SUB_CHANNELS:
                if ch and ch not in channels:
                    channels.append(ch)

        for i in range(1, 13):
            val = getattr(self, f"FORCE_SUB_{i}", None)
            if val and isinstance(val, str) and val.strip():
                clean = val.strip().strip("'\"")
                if clean and clean not in channels:
                    channels.append(clean)

        return channels[:12]


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
        """Returns True ONLY if user_id is in ADMIN_IDS."""
        if not self.ADMIN_IDS:
            return False
        return user_id in self.ADMIN_IDS

    def is_authorized(self, user_id: int) -> bool:
        """Returns True if the user is authorized to use the bot (all users if ADMINS_ONLY=False)."""
        if not self.ADMINS_ONLY:
            return True
        return self.is_admin(user_id)


def load_config() -> BotConfig:
    config = BotConfig()
    db_dir = Path(config.DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    return config

config = load_config()
