import asyncio
import logging
from typing import Dict, Any, List, Optional
from aiogram import Bot
from aiogram.types import (
    Message,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    InputMediaDocument
)
from aiogram.exceptions import (
    TelegramRetryAfter,
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramAPIError
)
from bot.config import config
from bot.database.models import StatsManager, RouteManager
from bot.services.transformer import MessageTransformer

logger = logging.getLogger(__name__)

class MessageDispatcher:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def forward_or_copy_message(
        self,
        message: Message,
        route: Dict[str, Any]
    ) -> bool:
        """
        Forward or copy a single message to destination chat.
        """
        route_id = route["id"]
        dest_chat_id = route["dest_chat_id"]
        dest_topic_id = route.get("dest_topic_id")
        forward_mode = route.get("forward_mode", "copy")

        # Load filters, customizations, replacements
        filters = await RouteManager.get_filters(route_id) or {}
        customizations = await RouteManager.get_customizations(route_id) or {}
        replacements = await RouteManager.get_replacements(route_id) or []

        # Check filtering
        can_forward, reason = MessageTransformer.should_forward(message, filters)
        if not can_forward:
            logger.info("Message %s skipped for route %s: %s", message.message_id, route_id, reason)
            await StatsManager.increment("total_filtered")
            return False

        # Transform text/caption
        orig_text = message.text or message.caption
        transformed_text = MessageTransformer.transform_text(
            orig_text, filters, customizations, replacements
        )

        protect_content = bool(customizations.get("protect_content", 0))
        pin = bool(customizations.get("pin_message", 0))

        # Attempt sending with retry mechanism
        for attempt in range(config.MAX_RETRIES):
            try:
                sent_msg = None
                if forward_mode == "forward":
                    # Native Telegram Forward
                    sent_msg = await self.bot.forward_message(
                        chat_id=dest_chat_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id,
                        message_thread_id=dest_topic_id,
                        protect_content=protect_content
                    )
                else:
                    # Clean Copy / Clone
                    # If message is standard text or media with caption
                    if message.text:
                        sent_msg = await self.bot.send_message(
                            chat_id=dest_chat_id,
                            text=transformed_text or message.text,
                            message_thread_id=dest_topic_id,
                            protect_content=protect_content,
                            disable_web_page_preview=False
                        )
                    else:
                        sent_msg = await self.bot.copy_message(
                            chat_id=dest_chat_id,
                            from_chat_id=message.chat.id,
                            message_id=message.message_id,
                            caption=transformed_text,
                            message_thread_id=dest_topic_id,
                            protect_content=protect_content
                        )

                if pin and sent_msg:
                    try:
                        await self.bot.pin_chat_message(
                            chat_id=dest_chat_id,
                            message_id=sent_msg.message_id,
                            disable_notification=True
                        )
                    except Exception as pin_err:
                        logger.warning("Could not pin message in %s: %s", dest_chat_id, pin_err)

                await StatsManager.increment("total_forwarded")
                logger.info("Successfully forwarded message %s to %s (route %s)", message.message_id, dest_chat_id, route_id)
                return True

            except TelegramRetryAfter as e:
                logger.warning("Telegram FloodWait hit for %s seconds. Retrying...", e.retry_after)
                await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError as e:
                logger.error("Forbidden error sending to %s (route %s): %s", dest_chat_id, route_id, e)
                await StatsManager.increment("total_errors")
                return False
            except TelegramBadRequest as e:
                logger.error("Bad Request error sending to %s (route %s): %s", dest_chat_id, route_id, e)
                await StatsManager.increment("total_errors")
                return False
            except TelegramAPIError as e:
                logger.error("Telegram API error (attempt %s/%s): %s", attempt + 1, config.MAX_RETRIES, e)
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error("Unexpected error forwarding message: %s", e, exc_info=True)
                await StatsManager.increment("total_errors")
                return False

        await StatsManager.increment("total_errors")
        return False

    async def forward_media_group(
        self,
        messages: List[Message],
        route: Dict[str, Any]
    ) -> bool:
        """
        Forward an entire media group (album) preserving grouping.
        """
        if not messages:
            return False

        route_id = route["id"]
        dest_chat_id = route["dest_chat_id"]
        dest_topic_id = route.get("dest_topic_id")
        forward_mode = route.get("forward_mode", "copy")

        first_msg = messages[0]
        filters = await RouteManager.get_filters(route_id) or {}
        customizations = await RouteManager.get_customizations(route_id) or {}
        replacements = await RouteManager.get_replacements(route_id) or []

        # Check filtering on primary message caption
        can_forward, reason = MessageTransformer.should_forward(first_msg, filters)
        if not can_forward:
            logger.info("Media group skipped for route %s: %s", route_id, reason)
            await StatsManager.increment("total_filtered")
            return False

        protect_content = bool(customizations.get("protect_content", 0))

        # If forward_mode is 'forward', forward each message in sequence
        if forward_mode == "forward":
            for msg in messages:
                await self.forward_or_copy_message(msg, route)
            return True

        # Clean Copy album using send_media_group
        media_group = []
        for idx, msg in enumerate(messages):
            transformed_caption = None
            if msg.caption:
                transformed_caption = MessageTransformer.transform_text(
                    msg.caption, filters, customizations, replacements
                )
            elif idx == 0:
                # If first image has no caption but header/footer exists
                transformed_caption = MessageTransformer.transform_text(
                    None, filters, customizations, replacements
                )

            if msg.photo:
                media_group.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=transformed_caption))
            elif msg.video:
                media_group.append(InputMediaVideo(media=msg.video.file_id, caption=transformed_caption))
            elif msg.audio:
                media_group.append(InputMediaAudio(media=msg.audio.file_id, caption=transformed_caption))
            elif msg.document:
                media_group.append(InputMediaDocument(media=msg.document.file_id, caption=transformed_caption))

        if not media_group:
            return False

        for attempt in range(config.MAX_RETRIES):
            try:
                await self.bot.send_media_group(
                    chat_id=dest_chat_id,
                    media=media_group,
                    message_thread_id=dest_topic_id,
                    protect_content=protect_content
                )
                await StatsManager.increment("total_forwarded", by=len(media_group))
                logger.info("Successfully forwarded album (%s items) to %s (route %s)", len(media_group), dest_chat_id, route_id)
                return True
            except TelegramRetryAfter as e:
                logger.warning("Telegram FloodWait hit for %s seconds. Retrying...", e.retry_after)
                await asyncio.sleep(e.retry_after + 1)
            except Exception as e:
                logger.error("Error sending media group: %s", e)
                await asyncio.sleep(2 ** attempt)

        await StatsManager.increment("total_errors")
        return False
