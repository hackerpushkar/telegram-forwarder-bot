import logging
from typing import List, Dict, Any, Tuple
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from bot.config import config

logger = logging.getLogger(__name__)

def parse_channel_info(raw: str, index: int = 1) -> Dict[str, Any]:
    """
    Parses a raw channel string from config into structured metadata.
    Supported formats:
      - "@channel_username"
      - "channel_username"
      - "https://t.me/channel_username"
      - "-1001234567890:https://t.me/+invitehash"
      - "-1001234567890"
    """
    raw = raw.strip()
    
    # Check for format "chat_id:invite_url"
    if ":" in raw and not (raw.startswith("http://") or raw.startswith("https://")):
        parts = raw.split(":", 1)
        chat_id_part = parts[0].strip()
        url_part = parts[1].strip()
        chat_id: Any = int(chat_id_part) if (chat_id_part.isdigit() or (chat_id_part.startswith("-") and chat_id_part[1:].isdigit())) else chat_id_part
        return {
            "index": index,
            "chat_id": chat_id,
            "url": url_part,
            "title": f"📢 Channel {index}",
            "raw": raw
        }

    # Handle https://t.me/ links
    if raw.startswith("https://t.me/") or raw.startswith("http://t.me/"):
        path = raw.split("t.me/", 1)[1].strip("/")
        if path.startswith("+") or path.startswith("joinchat/"):
            # Private invite link without explicit ID
            return {
                "index": index,
                "chat_id": raw,
                "url": raw,
                "title": f"📢 Channel {index}",
                "raw": raw
            }
        else:
            # Public username in link
            username = f"@{path}"
            return {
                "index": index,
                "chat_id": username,
                "url": f"https://t.me/{path}",
                "title": f"📢 {username}",
                "raw": raw
            }

    # Handle @username
    if raw.startswith("@"):
        username = raw
        clean_user = raw[1:]
        return {
            "index": index,
            "chat_id": username,
            "url": f"https://t.me/{clean_user}",
            "title": f"📢 {username}",
            "raw": raw
        }

    # Handle pure numeric chat_id
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        chat_id = int(raw)
        return {
            "index": index,
            "chat_id": chat_id,
            "url": "",
            "title": f"📢 Channel {index}",
            "raw": raw
        }

    # Plain username without @
    return {
        "index": index,
        "chat_id": f"@{raw}",
        "url": f"https://t.me/{raw}",
        "title": f"📢 @{raw}",
        "raw": raw
    }


def get_all_force_channels() -> List[Dict[str, Any]]:
    """Returns a list of parsed force subscribe channel dicts (max 12)."""
    raw_channels = config.get_configured_force_channels()
    parsed_channels = []
    for idx, raw in enumerate(raw_channels, 1):
        if raw:
            parsed_channels.append(parse_channel_info(raw, idx))
    return parsed_channels


async def check_force_sub(bot: Bot, user_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Checks if a user is subscribed to all configured force channels.
    Returns (is_subscribed, unjoined_channels_list).
    """
    channels = get_all_force_channels()
    if not channels:
        return True, []

    unjoined: List[Dict[str, Any]] = []

    for ch in channels:
        chat_id = ch["chat_id"]
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            
            # Check valid membership status
            status = member.status
            if status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER):
                continue
            elif status == ChatMemberStatus.RESTRICTED:
                # If restricted, check if they are still a member of the chat
                if getattr(member, "is_member", True):
                    continue
                else:
                    unjoined.append(ch)
            else:
                # LEFT, KICKED, BANNED
                unjoined.append(ch)

        except Exception as e:
            err_msg = str(e).lower()
            if "user not found" in err_msg or "participant" in err_msg or "chat not found" in err_msg:
                unjoined.append(ch)
            else:
                logger.warning("Error checking membership for user %s in channel %s: %s", user_id, chat_id, e)
                if "bot is not a member" in err_msg or "chat not found" in err_msg:
                    logger.error("Bot must be added as administrator in channel '%s' for Force Sub to work!", chat_id)
                else:
                    unjoined.append(ch)

    return len(unjoined) == 0, unjoined
