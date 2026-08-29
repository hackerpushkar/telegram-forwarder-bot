import asyncio
import logging
import os
import re
from typing import Optional, Dict, Any, Tuple
from telethon import TelegramClient, events, functions, types, utils
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PasswordHashInvalidError,
    UserAlreadyParticipantError,
    InviteHashExpiredError,
    InviteHashInvalidError
)

from bot.config import config
from bot.database.models import RouteManager, StatsManager, UserbotAuthManager
from bot.services.transformer import MessageTransformer

logger = logging.getLogger(__name__)

class UserbotManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(UserbotManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, bot_instance=None):
        if self._initialized:
            if bot_instance:
                self.bot = bot_instance
            return

        self.bot = bot_instance
        self.client: Optional[TelegramClient] = None
        self.phone_code_hash: Optional[str] = None
        self.pending_phone: Optional[str] = None
        self._is_running = False
        self._initialized = True

    async def initialize(self):
        """Initialize and start the host userbot if credentials and session exist."""
        if not config.API_ID or not config.API_HASH:
            logger.info("Host Userbot: API_ID or API_HASH not set in .env. Userbot auto-join will be available once configured.")
            return

        session_str = await UserbotAuthManager.get_session_string() or config.SESSION_STRING
        session = StringSession(session_str) if session_str else config.USERBOT_SESSION_NAME

        try:
            self.client = TelegramClient(session, config.API_ID, config.API_HASH)
            await self.client.connect()

            if await self.client.is_user_authorized():
                self._is_running = True
                me = await self.client.get_me()
                username_str = f"@{me.username}" if me.username else me.first_name
                logger.info("Host Userbot connected successfully as %s (ID: %s)", username_str, me.id)
                self._register_event_handlers()
                # Automatically ensure all active source channels/groups are joined
                asyncio.create_task(self.sync_and_join_all_active_sources())
            else:
                logger.info("Host Userbot: Client initialized but not authorized. Log in via /userbot command.")
        except Exception as e:
            logger.warning("Host Userbot initialization note: %s", e)

    def is_connected(self) -> bool:
        return self.client is not None and self.client.is_connected() and self._is_running

    async def sync_and_join_all_active_sources(self) -> int:
        """
        Iterate through all active routes in database and ensure Userbot is a participant
        in all source channels and groups.
        """
        if not self.is_connected():
            return 0

        logger.info("Syncing and joining all active source channels/groups for Userbot...")
        all_routes = await RouteManager.get_all_routes()
        active_ub_routes = [
            r for r in all_routes
            if r.get("is_active") and r.get("source_mode") == "userbot"
        ]

        joined_count = 0
        for route in active_ub_routes:
            src_id = route.get("source_chat_id")
            src_title = route.get("source_chat_title") or str(src_id)
            try:
                entity = await self.client.get_entity(src_id)
                if isinstance(entity, (types.Channel, types.Chat)):
                    try:
                        await self.client(functions.channels.JoinChannelRequest(channel=entity))
                        joined_count += 1
                    except UserAlreadyParticipantError:
                        pass
                    except Exception as e:
                        logger.info("Source channel status note (%s): %s", src_title, e)
            except Exception as e:
                logger.warning("Could not auto-sync source chat %s (%s): %s", src_title, src_id, e)

        logger.info("Userbot finished syncing active sources (%s channels/groups verified)", len(active_ub_routes))
        return joined_count

    async def get_me(self) -> Optional[Dict[str, Any]]:
        if not self.client or not await self.client.is_user_authorized():
            return None
        try:
            me = await self.client.get_me()
            return {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone
            }
        except Exception:
            return None

    # --- Interactive Host Login Flow ---

    async def send_login_code(self, phone: str) -> Tuple[bool, str]:
        if not config.API_ID or not config.API_HASH:
            return False, "API_ID and API_HASH are not set in .env! Please set them first."

        try:
            if not self.client:
                session = StringSession()
                self.client = TelegramClient(session, config.API_ID, config.API_HASH)
                await self.client.connect()
            elif not self.client.is_connected():
                await self.client.connect()

            clean_phone = phone.strip().replace(" ", "").replace("-", "")
            sent_code = await self.client.send_code_request(clean_phone)
            self.phone_code_hash = sent_code.phone_code_hash
            self.pending_phone = clean_phone
            return True, "Code sent successfully to Telegram app/SMS."
        except Exception as e:
            logger.error("Error sending host login code: %s", e)
            return False, f"Failed to send code: {str(e)}"

    async def sign_in_with_code(self, code: str, password: Optional[str] = None) -> Tuple[bool, str]:
        if not self.client or not self.pending_phone or not self.phone_code_hash:
            return False, "Login session expired. Please start over."

        clean_code = code.strip().replace(" ", "").replace("-", "")

        try:
            await self.client.sign_in(
                phone=self.pending_phone,
                code=clean_code,
                phone_code_hash=self.phone_code_hash
            )
        except SessionPasswordNeededError:
            if not password:
                return False, "2FA_REQUIRED"
            try:
                await self.client.sign_in(password=password)
            except PasswordHashInvalidError:
                return False, "Invalid 2FA password. Please try again."
        except PhoneCodeInvalidError:
            return False, "Invalid verification code. Please check and re-enter."
        except Exception as e:
            logger.error("Sign-in error: %s", e)
            return False, f"Sign in failed: {str(e)}"

        # Save session string to DB
        if isinstance(self.client.session, StringSession):
            session_str = self.client.session.save()
            await UserbotAuthManager.save_session_string(session_str)

        self._is_running = True
        self._register_event_handlers()
        
        # Automatically sync and join all active source channels/groups
        asyncio.create_task(self.sync_and_join_all_active_sources())

        me = await self.client.get_me()
        self.pending_phone = None
        self.phone_code_hash = None
        return True, f"Logged in as {me.first_name} (@{me.username or 'No username'})"

    async def logout(self) -> Tuple[bool, str]:
        if not self.client:
            return True, "Host Userbot is not running."
        try:
            await self.client.log_out()
            await UserbotAuthManager.clear_session()
            self._is_running = False
            return True, "Logged out successfully."
        except Exception as e:
            return False, f"Error logging out: {e}"

    # --- Auto-Join Channel / Group ---

    async def join_chat(self, chat_input: Any) -> Tuple[Optional[int], Optional[str], Optional[str], Optional[str]]:
        """
        Silently auto-joins channel/group via username, invite link, or chat ID.
        Returns (chat_id, title, username, error_msg)
        """
        if not self.is_connected():
            return None, None, None, "Host Userbot is not connected. The bot owner must log in via /userbot first."

        if isinstance(chat_input, (int, float)):
            target = int(chat_input)
            try:
                entity = await self.client.get_entity(target)
                if isinstance(entity, (types.Channel, types.Chat)):
                    try:
                        await self.client(functions.channels.JoinChannelRequest(channel=entity))
                    except UserAlreadyParticipantError:
                        pass
                    except Exception as join_err:
                        logger.info("Join note for %s: %s", target, join_err)

                    chat_id = utils.get_peer_id(entity)
                    title = getattr(entity, "title", str(entity.id))
                    username = getattr(entity, "username", None)
                    return chat_id, title, username, None
            except Exception as e:
                return None, None, None, f"Could not access chat ID {target}: {e}"

        clean_input = str(chat_input).strip()

        # 1. Handle private invite links (t.me/+hash, t.me/joinchat/hash, +hash)
        invite_match = re.search(
            r'(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:me|dog))/(?:\+|joinchat/)([\w-]+)|^\+([\w-]+)$',
            clean_input
        )
        if invite_match:
            invite_hash = invite_match.group(1) or invite_match.group(2)
            try:
                updates = await self.client(functions.messages.ImportChatInviteRequest(hash=invite_hash))
                chats = getattr(updates, "chats", [])
                if chats:
                    chat = chats[0]
                    chat_id = utils.get_peer_id(chat)
                    return chat_id, getattr(chat, 'title', 'Channel'), getattr(chat, 'username', None), None
                # If updates didn't have chats list, check invite
                check = await self.client(functions.messages.CheckChatInviteRequest(hash=invite_hash))
                chat = getattr(check, 'chat', check)
                chat_id = utils.get_peer_id(chat) if hasattr(chat, 'id') else None
                return chat_id, getattr(chat, 'title', 'Channel'), getattr(chat, 'username', None), None
            except UserAlreadyParticipantError:
                try:
                    check = await self.client(functions.messages.CheckChatInviteRequest(hash=invite_hash))
                    chat = getattr(check, 'chat', check)
                    chat_id = utils.get_peer_id(chat) if hasattr(chat, 'id') else None
                    title = getattr(chat, 'title', 'Channel')
                    username = getattr(chat, 'username', None)
                    return chat_id, title, username, None
                except Exception as e:
                    return None, None, None, f"Already in channel, but could not resolve ID: {e}"
            except (InviteHashExpiredError, InviteHashInvalidError):
                return None, None, None, "The invite link has expired or is invalid."
            except Exception as e:
                return None, None, None, f"Could not join private invite link: {e}"

        # 2. Handle pure numeric IDs
        if clean_input.lstrip("-").isdigit():
            try:
                target_id = int(clean_input)
                entity = await self.client.get_entity(target_id)
                if isinstance(entity, (types.Channel, types.Chat)):
                    try:
                        await self.client(functions.channels.JoinChannelRequest(channel=entity))
                    except UserAlreadyParticipantError:
                        pass
                    except Exception as join_err:
                        logger.info("Join note for numeric ID %s: %s", target_id, join_err)

                    chat_id = utils.get_peer_id(entity)
                    title = getattr(entity, "title", str(entity.id))
                    username = getattr(entity, "username", None)
                    return chat_id, title, username, None
            except Exception as e:
                return None, None, None, f"Could not find chat ID '{clean_input}': {e}"

        # 3. Handle public usernames (@username or t.me/username)
        username_match = re.search(r'(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:me|dog))/([a-zA-Z0-9_]{4,})|@([a-zA-Z0-9_]{4,})', clean_input)
        target = (username_match.group(1) or username_match.group(2)) if username_match else clean_input.lstrip("@")

        try:
            entity = await self.client.get_entity(target)
            
            if isinstance(entity, (types.Channel, types.Chat)):
                try:
                    await self.client(functions.channels.JoinChannelRequest(channel=entity))
                except UserAlreadyParticipantError:
                    pass
                except Exception as join_err:
                    logger.info("Join note for %s: %s", target, join_err)

                chat_id = utils.get_peer_id(entity)
                title = getattr(entity, "title", str(entity.id))
                username = getattr(entity, "username", None)
                return chat_id, title, username, None

            return None, None, None, "Target is not a channel or group."
        except Exception as e:
            return None, None, None, f"Failed to find or join '{target}': {str(e)}"

    # --- Live Message Listener ---

    def _register_event_handlers(self):
        if not self.client:
            return

        @self.client.on(events.NewMessage)
        async def userbot_message_handler(event: events.NewMessage.Event):
            if not event.chat_id:
                return

            chat_id = event.chat_id
            routes = await RouteManager.get_active_routes_for_source(chat_id, source_mode="userbot")
            if not routes:
                return

            logger.info("Host Userbot received message from %s (matched %s routes)", chat_id, len(routes))

            for route in routes:
                try:
                    await self._process_userbot_forward(event, route)
                except Exception as e:
                    logger.error("Error dispatching userbot message for route %s: %s", route["id"], e, exc_info=True)

    async def _process_userbot_forward(self, event: events.NewMessage.Event, route: Dict[str, Any]):
        route_id = route["id"]
        dest_chat_id = route["dest_chat_id"]
        dest_topic_id = route.get("dest_topic_id")
        forward_mode = route.get("forward_mode", "copy")

        filters = await RouteManager.get_filters(route_id) or {}
        customizations = await RouteManager.get_customizations(route_id) or {}
        replacements = await RouteManager.get_replacements(route_id) or []

        msg_text = event.message.message or ""

        # Whitelist & Blacklist Keyword Filtering
        whitelist_raw = filters.get("keyword_whitelist") or ""
        blacklist_raw = filters.get("keyword_blacklist") or ""

        if blacklist_raw.strip():
            blacklist_kws = [k.strip().lower() for k in re.split(r'[,\n]', blacklist_raw) if k.strip()]
            for kw in blacklist_kws:
                if kw in msg_text.lower():
                    logger.info("Message skipped: matched blacklist keyword '%s'", kw)
                    await StatsManager.increment("total_filtered")
                    return

        if whitelist_raw.strip():
            whitelist_kws = [k.strip().lower() for k in re.split(r'[,\n]', whitelist_raw) if k.strip()]
            if whitelist_kws and not any(kw in msg_text.lower() for kw in whitelist_kws):
                logger.info("Message skipped: no whitelist keyword matched")
                await StatsManager.increment("total_filtered")
                return

        # Transform text / caption
        transformed_text = MessageTransformer.transform_text(
            msg_text, filters, customizations, replacements
        )

        protect_content = bool(customizations.get("protect_content", 0))

        # Delivery via Bot API into user's destination channel
        if self.bot:
            try:
                if event.message.media:
                    # Download media into memory / temp and send via Bot
                    media_bytes = await self.client.download_media(event.message.media, bytes)
                    if media_bytes:
                        from aiogram.types import BufferedInputFile
                        input_file = BufferedInputFile(media_bytes, filename="media.jpg")
                        if isinstance(event.message.media, types.MessageMediaPhoto):
                            await self.bot.send_photo(
                                chat_id=dest_chat_id,
                                photo=input_file,
                                caption=transformed_text,
                                message_thread_id=dest_topic_id,
                                protect_content=protect_content
                            )
                        elif isinstance(event.message.media, types.MessageMediaDocument):
                            await self.bot.send_document(
                                chat_id=dest_chat_id,
                                document=input_file,
                                caption=transformed_text,
                                message_thread_id=dest_topic_id,
                                protect_content=protect_content
                            )
                        else:
                            await self.bot.send_message(
                                chat_id=dest_chat_id,
                                text=transformed_text or msg_text,
                                message_thread_id=dest_topic_id,
                                protect_content=protect_content
                            )
                else:
                    await self.bot.send_message(
                        chat_id=dest_chat_id,
                        text=transformed_text or msg_text,
                        message_thread_id=dest_topic_id,
                        protect_content=protect_content
                    )

                await StatsManager.increment("total_forwarded")
                await StatsManager.increment("userbot_forwarded")
                logger.info("Bot successfully delivered userbot post to %s (route %s)", dest_chat_id, route_id)
                return
            except Exception as bot_err:
                logger.warning("Bot delivery failed (%s). Falling back to Userbot delivery...", bot_err)

        # Fallback to Userbot direct send
        try:
            if forward_mode == "forward":
                await self.client.forward_messages(entity=dest_chat_id, messages=event.message)
            else:
                if event.message.media:
                    await self.client.send_file(entity=dest_chat_id, file=event.message.media, caption=transformed_text or "")
                else:
                    await self.client.send_message(entity=dest_chat_id, message=transformed_text or msg_text)

            await StatsManager.increment("total_forwarded")
            await StatsManager.increment("userbot_forwarded")
            logger.info("Host Userbot forwarded post to %s (route %s)", dest_chat_id, route_id)
        except Exception as e:
            logger.error("Failed to forward post to %s: %s", dest_chat_id, e)
            await StatsManager.increment("total_errors")

userbot_manager = UserbotManager()
