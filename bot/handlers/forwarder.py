import logging
from typing import List, Optional
from aiogram import Router, F
from aiogram.types import Message
from bot.database.models import RouteManager
from bot.services.sender import MessageDispatcher

logger = logging.getLogger(__name__)

router = Router(name="forwarder_router")

@router.channel_post()
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_incoming_source_message(
    message: Message,
    album: Optional[List[Message]] = None
):
    """
    Main listener for all incoming channel posts and group messages.
    Finds any active routes matching the source chat and forwards the message/album.
    """
    source_chat_id = message.chat.id
    source_topic_id = message.message_thread_id

    # Retrieve all active routes configured for this source chat
    routes = await RouteManager.get_active_routes_for_source(
        source_chat_id=source_chat_id,
        source_topic_id=source_topic_id
    )

    if not routes:
        return

    dispatcher = MessageDispatcher(message.bot)

    for route in routes:
        try:
            if album:
                await dispatcher.forward_media_group(album, route)
            else:
                await dispatcher.forward_or_copy_message(message, route)
        except Exception as e:
            logger.error("Error executing route %s for message %s: %s", route["id"], message.message_id, e, exc_info=True)
