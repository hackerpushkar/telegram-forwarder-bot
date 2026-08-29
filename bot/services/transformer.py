import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from aiogram.types import Message

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r'https?://\S+|www\.\S+|t\.me/\S+', re.IGNORECASE)
USERNAME_PATTERN = re.compile(r'@\w+', re.IGNORECASE)

class MessageTransformer:
    @staticmethod
    def get_message_content_type(message: Message) -> str:
        if message.text:
            return "text"
        elif message.photo:
            return "photo"
        elif message.video:
            return "video"
        elif message.document:
            return "document"
        elif message.audio:
            return "audio"
        elif message.voice:
            return "voice"
        elif message.animation:
            return "animation"
        elif message.sticker:
            return "sticker"
        elif message.poll:
            return "poll"
        elif message.video_note:
            return "video_note"
        elif message.contact:
            return "contact"
        elif message.location:
            return "location"
        return "other"

    @staticmethod
    def should_forward(
        message: Message,
        filters: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a message should be forwarded according to media filters and keyword rules.
        Returns (should_forward, reason_if_skipped)
        """
        content_type = MessageTransformer.get_message_content_type(message)

        # 1. Media Type Filter
        filter_col_map = {
            "text": "allow_text",
            "photo": "allow_photo",
            "video": "allow_video",
            "document": "allow_document",
            "audio": "allow_audio",
            "voice": "allow_voice",
            "animation": "allow_animation",
            "sticker": "allow_sticker",
            "poll": "allow_poll"
        }

        col = filter_col_map.get(content_type)
        if col and not filters.get(col, 1):
            return False, f"Filtered out: {content_type} media type disabled"

        # 2. Extract Text / Caption
        raw_text = message.text or message.caption or ""
        
        # 3. Keyword Whitelist & Blacklist
        whitelist_raw = filters.get("keyword_whitelist") or ""
        blacklist_raw = filters.get("keyword_blacklist") or ""

        # Blacklist check
        if blacklist_raw.strip():
            blacklist_keywords = [k.strip().lower() for k in re.split(r'[,\n]', blacklist_raw) if k.strip()]
            for kw in blacklist_keywords:
                if kw in raw_text.lower():
                    return False, f"Filtered out: matched blacklisted keyword '{kw}'"

        # Whitelist check (if specified, message MUST contain at least one)
        if whitelist_raw.strip():
            whitelist_keywords = [k.strip().lower() for k in re.split(r'[,\n]', whitelist_raw) if k.strip()]
            if whitelist_keywords:
                matched = any(kw in raw_text.lower() for kw in whitelist_keywords)
                if not matched:
                    return False, "Filtered out: no whitelisted keywords matched"

        return True, None

    @staticmethod
    def transform_text(
        text: Optional[str],
        filters: Dict[str, Any],
        customizations: Dict[str, Any],
        replacements: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Transform text or caption according to filters, replacements, and customizations.
        """
        if text is None:
            # If there was no text, we can still add header/footer if they exist
            header = (customizations.get("header_text") or "").strip()
            footer = (customizations.get("footer_text") or "").strip()
            if header or footer:
                parts = [p for p in [header, footer] if p]
                return "\n\n".join(parts)
            return None

        result = text

        # 1. Apply Find & Replace list
        for rep in replacements:
            find_txt = rep.get("find_text", "")
            replace_txt = rep.get("replace_text", "")
            is_regex = bool(rep.get("is_regex", 0))

            if not find_txt:
                continue

            if is_regex:
                try:
                    result = re.sub(find_txt, replace_txt, result)
                except Exception as e:
                    logger.warning("Regex error for pattern '%s': %s", find_txt, e)
            else:
                result = result.replace(find_txt, replace_txt)

        # 2. Remove Links if enabled
        if filters.get("remove_links", 0):
            result = URL_PATTERN.sub("", result)

        # 3. Remove Usernames if enabled
        if filters.get("remove_usernames", 0):
            result = USERNAME_PATTERN.sub("", result)

        # Clean multiple spaces/blank lines leftover from removals
        result = result.strip()

        # 4. Apply Header & Footer
        header = (customizations.get("header_text") or "").strip()
        footer = (customizations.get("footer_text") or "").strip()

        parts = []
        if header:
            parts.append(header)
        if result:
            parts.append(result)
        if footer:
            parts.append(footer)

        final_text = "\n\n".join(parts) if parts else None
        return final_text
