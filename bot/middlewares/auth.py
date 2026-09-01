from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from bot.config import config

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Check if event is from a private chat user
        user_id = None
        if isinstance(event, Message):
            if event.chat.type == "private" and event.from_user:
                user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        # If it's a private chat interaction, check authorization
        if user_id is not None:
            if not config.is_authorized(user_id):
                if isinstance(event, Message):
                    await event.answer(
                        "⛔ <b>Access Denied</b>\n\n"
                        "This bot is configured in restricted mode. Only authorized administrators can configure forwarding routes.\n\n"
                        f"Your User ID: <code>{user_id}</code>",
                        parse_mode="HTML"
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer("⛔ Access Denied. You are not authorized to use this bot.", show_alert=True)
                return

        return await handler(event, data)
