import asyncio
from typing import Callable, Dict, Any, Awaitable, List
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.6):
        self.latency = latency
        self.albums: Dict[str, List[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message) or not event.media_group_id:
            return await handler(event, data)

        media_group_id = str(event.media_group_id)

        try:
            self.albums[media_group_id].append(event)
            # This is not the first message of the album, so skip handler execution
            return
        except KeyError:
            # First message of the album
            self.albums[media_group_id] = [event]
            await asyncio.sleep(self.latency)

            # Get collected album messages
            data["album"] = self.albums.pop(media_group_id, [event])
            return await handler(event, data)
