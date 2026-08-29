import re
from typing import Optional, Tuple
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards.inline import (
    get_routes_list_kb,
    get_route_details_kb,
    get_confirm_delete_kb,
    get_forward_mode_kb,
    get_cancel_kb,
    get_main_menu_kb
)
from bot.database.models import RouteManager
from bot.services.userbot import userbot_manager

router = Router(name="routes_manager_router")

class RouteWizardState(StatesGroup):
    name = State()
    source = State()
    dest = State()
    mode = State()

class RenameRouteState(StatesGroup):
    route_id = State()
    page = State()
    new_name = State()

async def resolve_chat_input(bot, text: Optional[str], message: Message) -> Tuple[Optional[int], Optional[str], Optional[str], Optional[int]]:
    """
    Resolves chat input from direct text/username/id or a forwarded message.
    Returns (chat_id, title_or_username, chat_type, message_thread_id)
    """
    # 1. Check if user forwarded a message from a channel or chat
    if message.forward_from_chat:
        f_chat = message.forward_from_chat
        return f_chat.id, f_chat.title or f_chat.username or str(f_chat.id), f_chat.type, message.message_thread_id

    if not text:
        return None, None, None, None

    clean_text = text.strip()
    if clean_text.startswith("https://t.me/"):
        clean_text = "@" + clean_text.replace("https://t.me/", "").split("/")[0]

    # Try resolving via Bot API if possible
    try:
        if clean_text.startswith("@") or clean_text.startswith("-") or clean_text.isdigit():
            chat = await bot.get_chat(clean_text)
            return chat.id, chat.title or chat.username or str(chat.id), chat.type, None
    except Exception:
        pass

    # Pure numeric ID
    if clean_text.lstrip("-").isdigit():
        return int(clean_text), f"Chat {clean_text}", "channel", None

    return None, None, None, None

# --- Routes Listing ---

@router.message(Command("routes"))
@router.message(Command("list"))
async def cmd_routes(message: Message):
    routes = await RouteManager.get_routes_by_user(message.from_user.id)
    if not routes:
        routes = await RouteManager.get_all_routes()

    if not routes:
        await message.answer(
            "📭 <b>No Forwarding Routes Found!</b>\n\n"
            "You haven't set up any forward routes yet.\n"
            "Click <b>'➕ Add New Route'</b> to create your first one.",
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(message.from_user.id)
        )
        return

    await message.answer(
        f"📋 <b>Your Forwarding Routes ({len(routes)} Total)</b>\n\n"
        "Click on any route below to view details, configure filters, or toggle active state:",
        parse_mode="HTML",
        reply_markup=get_routes_list_kb(routes, page=0)
    )

@router.callback_query(F.data.startswith("routes:list:"))
async def cb_routes_list(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    routes = await RouteManager.get_routes_by_user(callback.from_user.id)
    if not routes:
        routes = await RouteManager.get_all_routes()

    if not routes:
        await callback.message.edit_text(
            "📭 <b>No Forwarding Routes Found!</b>\n\n"
            "Click <b>'➕ Add New Route'</b> to create your first route.",
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(callback.from_user.id)
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📋 <b>Your Forwarding Routes ({len(routes)} Total)</b>\n\n"
        "Click on any route below to view details, configure filters, or toggle active state:",
        parse_mode="HTML",
        reply_markup=get_routes_list_kb(routes, page=page)
    )
    await callback.answer()

# --- View Single Route ---

@router.callback_query(F.data.startswith("route:view:"))
async def cb_route_view(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    route = await RouteManager.get_route(route_id)
    if not route:
        await callback.answer("❌ Route not found!", show_alert=True)
        return

    status_badge = "🟢 <b>ACTIVE</b>" if route["is_active"] else "🔴 <b>PAUSED</b>"
    mode_badge = "📋 <b>Clean Copy (Clone)</b>" if route.get("forward_mode") == "copy" else "⏩ <b>Native Forward</b>"
    src_mode = "👤 <b>Auto-Joined Source</b>" if route.get("source_mode") == "userbot" else "🤖 <b>Bot Admin Mode</b>"

    text = f"""
🛠️ <b>Route Details: {route['name']}</b>

• <b>Status:</b> {status_badge}
• <b>Forward Mode:</b> {mode_badge}
• <b>Source Link:</b> {src_mode}

📥 <b>Source ({route.get('source_chat_type', 'chat').upper()}):</b>
  • Title: <code>{route.get('source_chat_title') or 'N/A'}</code>
  • Chat ID: <code>{route['source_chat_id']}</code>
  • Topic ID: <code>{route.get('source_topic_id') or 'General'}</code>

📤 <b>Destination ({route.get('dest_chat_type', 'chat').upper()}):</b>
  • Title: <code>{route.get('dest_chat_title') or 'N/A'}</code>
  • Chat ID: <code>{route['dest_chat_id']}</code>
  • Topic ID: <code>{route.get('dest_topic_id') or 'General'}</code>

<i>Use buttons below to customize filters, header/footer, or toggle route:</i>
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_route_details_kb(route, page=page)
    )
    await callback.answer()

# --- Toggle Active State ---

@router.callback_query(F.data.startswith("route:toggle:"))
async def cb_route_toggle(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    new_state = await RouteManager.toggle_route_active(route_id)
    state_str = "Resumed 🟢" if new_state else "Paused 🔴"
    await callback.answer(f"Route {state_str}")
    await cb_route_view(callback)

# --- Toggle Forward Mode ---

@router.callback_query(F.data.startswith("route:mode:"))
async def cb_route_mode(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    route = await RouteManager.get_route(route_id)
    if route:
        new_mode = "forward" if route.get("forward_mode") == "copy" else "copy"
        await RouteManager.update_forward_mode(route_id, new_mode)
        mode_label = "Clean Copy 📋" if new_mode == "copy" else "Native Forward ⏩"
        await callback.answer(f"Switched mode to {mode_label}")

    await cb_route_view(callback)

# --- Delete Route ---

@router.callback_query(F.data.startswith("route:delete_confirm:"))
async def cb_route_delete_confirm(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    route = await RouteManager.get_route(route_id)
    if not route:
        await callback.answer("Route not found!", show_alert=True)
        return

    text = f"⚠️ <b>Are you sure you want to delete route '{route['name']}'?</b>\n\nThis will remove all associated filters and settings permanently."
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_confirm_delete_kb(route_id, page=page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("route:delete_do:"))
async def cb_route_delete_do(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    await RouteManager.delete_route(route_id)
    await callback.answer("Route deleted successfully! 🗑️", show_alert=True)
    await cb_routes_list(callback)

# --- Rename Route ---

@router.callback_query(F.data.startswith("route:rename:"))
async def cb_route_rename(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    await state.set_state(RenameRouteState.new_name)
    await state.update_data(route_id=route_id, page=page)

    await callback.message.edit_text(
        "✏️ <b>Enter new name for this route:</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )
    await callback.answer()

@router.message(RenameRouteState.new_name)
async def process_rename_route(message: Message, state: FSMContext):
    new_name = message.text.strip() if message.text else ""
    if not new_name:
        await message.answer("⚠️ Name cannot be empty. Please enter a valid name:")
        return

    data = await state.get_data()
    route_id = data["route_id"]
    page = data["page"]

    await RouteManager.update_route_name(route_id, new_name)
    await state.clear()

    route = await RouteManager.get_route(route_id)
    await message.answer(f"✅ Route renamed to <b>{new_name}</b>!", parse_mode="HTML")
    await message.answer(
        text="Route details:",
        reply_markup=get_route_details_kb(route, page=page)
    )

# --- Streamlined 4-Step Route Creation Wizard ---

@router.message(Command("newroute"))
@router.message(Command("add"))
@router.callback_query(F.data == "wizard:start")
async def start_new_route_wizard(event, state: FSMContext):
    await state.clear()
    await state.set_state(RouteWizardState.name)

    text = """
✨ <b>Create New Forwarding Route — Step 1/4</b>

Please enter a <b>friendly name</b> for this route:
<i>(Example: 'Crypto Signals to VIP' or 'Public News ➔ My Channel')</i>
"""
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
        await event.answer()
    else:
        await event.answer(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())

@router.callback_query(F.data == "wizard:cancel")
async def cb_wizard_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Operation Cancelled</b>",
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(callback.from_user.id)
    )
    await callback.answer()

@router.message(RouteWizardState.name)
async def process_wizard_name(message: Message, state: FSMContext):
    name = message.text.strip() if message.text else "Forward Route"
    await state.update_data(name=name)
    await state.set_state(RouteWizardState.source)

    text = f"""
📥 <b>Step 2/4: Set SOURCE Channel or Group</b>
Route: <b>{name}</b>

Provide the <b>SOURCE</b> where messages originate:

🌐 <b>Public Channel / Group:</b>
• Enter username (e.g. <code>@source_channel</code> or <code>https://t.me/source_channel</code>)
• Or simply <b>forward a message</b> here from the public chat!

🔒 <b>Private Channel / Group:</b>
• <b>Invite Link Required:</b> Enter invite link (e.g. <code>https://t.me/+join_hash</code>)
<i>(Note: For private channels/groups, an invite link is required so the Host Userbot can join. Forwarding a message or numeric ID alone cannot grant access to a private chat.)</i>

<i>✨ Our system will automatically connect and listen to incoming posts!</i>
"""
    await message.answer(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())

async def is_bot_admin_in_chat(bot, chat_id: Optional[int]) -> bool:
    """Checks whether the bot is an administrator/creator in the given chat."""
    if not chat_id:
        return False
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=bot.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

@router.message(RouteWizardState.source)
async def process_wizard_source(message: Message, state: FSMContext):
    raw_input = message.text.strip() if message.text else ""
    wait_msg = await message.answer("⏳ <i>Connecting to source chat...</i>", parse_mode="HTML")

    chat_id = None
    title = None
    chat_type = "channel"
    topic_id = None
    source_mode = "bot"

    # Check if input is a private invite link (t.me/+hash, t.me/joinchat/hash, +hash)
    is_invite_link = bool(re.search(
        r'(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:me|dog))/(?:\+|joinchat/)([\w-]+)|^\+([\w-]+)$',
        raw_input
    ))

    # Case 1: User sent an invite link
    if is_invite_link:
        if not userbot_manager.is_connected():
            await wait_msg.edit_text(
                "⚠️ <b>Host Userbot is Disconnected!</b>\n\n"
                "To join invite links automatically, the Host Userbot must be logged in.\n"
                "Please ask the bot owner to connect the Host Userbot via <code>/userbot</code>, or add this bot as an Admin directly in the source chat.",
                parse_mode="HTML",
                reply_markup=get_cancel_kb()
            )
            return

        ub_chat_id, ub_title, ub_username, ub_error = await userbot_manager.join_chat(raw_input)
        if ub_chat_id:
            chat_id = ub_chat_id
            title = ub_title or raw_input
            chat_type = "channel"
            source_mode = "userbot"
        else:
            await wait_msg.edit_text(
                f"❌ <b>Could not join invite link:</b>\n{ub_error or 'Link invalid or expired'}\n\nPlease check the link and try again:",
                parse_mode="HTML",
                reply_markup=get_cancel_kb()
            )
            return

    # Case 2: User forwarded a message from a source channel or group
    elif message.forward_from_chat:
        f_chat = message.forward_from_chat
        chat_id = f_chat.id
        title = f_chat.title or f_chat.username or str(f_chat.id)
        chat_type = f_chat.type
        topic_id = message.message_thread_id

        # Check if Bot is already an Admin in this chat
        if await is_bot_admin_in_chat(message.bot, chat_id):
            source_mode = "bot"
        else:
            # Bot is not an Admin; Userbot must join/listen
            if not userbot_manager.is_connected():
                await wait_msg.edit_text(
                    f"⚠️ <b>Bot is not an Admin in '{title}'!</b>\n\n"
                    "Telegram Bot API cannot read posts from channels where the bot is not an Administrator.\n\n"
                    "<b>To fix this, choose one option:</b>\n"
                    f"1. Add this bot as an <b>Admin</b> in <b>{title}</b>, OR\n"
                    "2. Log in the Host Userbot via <code>/userbot</code> so it can auto-join and forward messages for you.",
                    parse_mode="HTML",
                    reply_markup=get_cancel_kb()
                )
                return

            # If the forwarded chat has a public username, userbot joins via @username
            if f_chat.username:
                ub_chat_id, ub_title, ub_username, ub_error = await userbot_manager.join_chat(f"@{f_chat.username}")
                if ub_chat_id:
                    chat_id = ub_chat_id
                    title = ub_title or title
                    source_mode = "userbot"
                else:
                    await wait_msg.edit_text(
                        f"❌ <b>Userbot could not join '{title}':</b>\n{ub_error}\n\nPlease try sending the invite link directly:",
                        parse_mode="HTML",
                        reply_markup=get_cancel_kb()
                    )
                    return
            else:
                # Private channel/group without public username
                ub_chat_id, ub_title, ub_username, ub_error = await userbot_manager.join_chat(chat_id)
                if ub_chat_id:
                    chat_id = ub_chat_id
                    title = ub_title or title
                    source_mode = "userbot"
                else:
                    await wait_msg.edit_text(
                        f"🔒 <b>Private Channel/Group Detected: '{title}'</b>\n\n"
                        "This forwarded message is from a <b>private chat</b> without a public username.\n"
                        "Forwarded messages alone do not grant access to private chats.\n\n"
                        "👉 <b>Please send an Invite Link</b> (e.g. <code>https://t.me/+join_hash</code>) so the Host Userbot can join and listen to posts:",
                        parse_mode="HTML",
                        reply_markup=get_cancel_kb()
                    )
                    return

    # Case 3: User provided text (public username, link, or numeric ID)
    else:
        # Check if direct numeric ID
        is_numeric_id = raw_input.lstrip("-").isdigit()

        # Try resolving chat details via Bot API
        res_chat_id, res_title, res_type, res_topic = await resolve_chat_input(message.bot, message.text, message)
        
        # Check if Bot is already an Admin in this chat
        if res_chat_id and await is_bot_admin_in_chat(message.bot, res_chat_id):
            chat_id = res_chat_id
            title = res_title or raw_input
            chat_type = res_type or "channel"
            topic_id = res_topic
            source_mode = "bot"
        else:
            # Bot is not an Admin; Userbot must join and listen
            if userbot_manager.is_connected():
                ub_chat_id, ub_title, ub_username, ub_error = await userbot_manager.join_chat(raw_input)
                if ub_chat_id:
                    chat_id = ub_chat_id
                    title = ub_title or ub_username or res_title or raw_input
                    chat_type = res_type or "channel"
                    topic_id = res_topic
                    source_mode = "userbot"
                else:
                    if is_numeric_id:
                        await wait_msg.edit_text(
                            f"🔒 <b>Private Chat Detected (ID: <code>{raw_input}</code>)</b>\n\n"
                            "Telegram does not permit joining private chats using only a Chat ID.\n\n"
                            "👉 <b>Please send an Invite Link</b> (e.g. <code>https://t.me/+join_hash</code>) so the Host Userbot can join:",
                            parse_mode="HTML",
                            reply_markup=get_cancel_kb()
                        )
                    else:
                        await wait_msg.edit_text(
                            f"❌ <b>Could not connect to source:</b>\n{ub_error or 'Chat not found'}\n\nPlease check the link/username or send an invite link:",
                            parse_mode="HTML",
                            reply_markup=get_cancel_kb()
                        )
                    return
            else:
                if res_chat_id:
                    await wait_msg.edit_text(
                        f"⚠️ <b>Bot is not an Admin in '{res_title or raw_input}'!</b>\n\n"
                        "Telegram Bot API cannot receive posts from channels where the bot is not an Administrator.\n\n"
                        "<b>To fix this, choose one option:</b>\n"
                        f"1. Add this bot as an <b>Admin</b> in <b>{res_title or raw_input}</b>, OR\n"
                        "2. Log in the Host Userbot via <code>/userbot</code> so it can auto-join and forward messages for you.",
                        parse_mode="HTML",
                        reply_markup=get_cancel_kb()
                    )
                else:
                    if is_numeric_id:
                        await wait_msg.edit_text(
                            f"🔒 <b>Private Chat Detected (ID: <code>{raw_input}</code>)</b>\n\n"
                            "Telegram does not permit joining private chats using only a numeric ID.\n\n"
                            "👉 <b>Please send an Invite Link</b> (e.g. <code>https://t.me/+join_hash</code>):",
                            parse_mode="HTML",
                            reply_markup=get_cancel_kb()
                        )
                    else:
                        await wait_msg.edit_text(
                            "⚠️ <b>Could not access source chat!</b>\n\n"
                            "• If this is your channel/group, make sure to add this bot as an <b>Admin</b>.\n"
                            "• If this is a public/other channel, ask the bot owner to connect the Host Userbot via <code>/userbot</code>.\n\n"
                            "Please provide a valid <code>@username</code>, invite link, or forwarded message:",
                            parse_mode="HTML",
                            reply_markup=get_cancel_kb()
                        )
                return

    mode_label = "👤 Auto-Joined Userbot" if source_mode == "userbot" else "🤖 Bot Admin"

    await state.update_data(
        source_chat_id=chat_id,
        source_chat_title=title or raw_input,
        source_chat_type=chat_type or "channel",
        source_topic_id=topic_id,
        source_mode=source_mode
    )
    await state.set_state(RouteWizardState.dest)

    text = f"""
📤 <b>Step 3/4: Set DESTINATION Channel or Group</b>
Source Connected: <b>{title or raw_input}</b> 🟢
Mode: <i>{mode_label}</i>

Now provide the <b>DESTINATION</b> chat where messages should be sent:
• <b>Option A:</b> Enter public username (e.g. <code>@dest_channel</code>)
• <b>Option B:</b> Enter numeric Chat ID (e.g. <code>-1009876543210</code>)
• <b>Option C:</b> Simply <b>forward a message</b> here from the destination chat!

<i>⚠️ Ensure this bot is an <b>ADMINISTRATOR</b> with <b>Post Messages / Send Messages</b> permission in the destination!</i>
"""
    await wait_msg.edit_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())

@router.message(RouteWizardState.dest)
async def process_wizard_dest(message: Message, state: FSMContext):
    chat_id, title, chat_type, topic_id = await resolve_chat_input(message.bot, message.text, message)

    if not chat_id:
        await message.answer(
            "⚠️ <b>Could not resolve Destination Chat!</b>\n\n"
            "Please provide a valid <code>@username</code>, numeric chat ID (e.g. <code>-100...</code>), or forward a message directly from the destination chat.",
            parse_mode="HTML",
            reply_markup=get_cancel_kb()
        )
        return

    await state.update_data(
        dest_chat_id=chat_id,
        dest_chat_title=title,
        dest_chat_type=chat_type,
        dest_topic_id=topic_id
    )
    await state.set_state(RouteWizardState.mode)

    text = f"""
⚙️ <b>Step 4/4: Choose Forwarding Mode</b>

• <b>Clean Copy (Clone):</b> Sends clean messages without the original sender/channel header tag. Supports header/footer watermarks and word replacement.
• <b>Native Forward:</b> Standard Telegram forward that retains original sender/channel attribution.

Select mode below:
"""
    await message.answer(text=text, parse_mode="HTML", reply_markup=get_forward_mode_kb())

@router.callback_query(F.data.startswith("wiz:mode:"))
async def process_wizard_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[2]  # "copy" or "forward"
    data = await state.get_data()

    user_id = callback.from_user.id
    name = data.get("name", "Forward Route")
    source_chat_id = data["source_chat_id"]
    source_chat_title = data.get("source_chat_title", "")
    source_chat_type = data.get("source_chat_type", "channel")
    source_topic_id = data.get("source_topic_id")
    source_mode = data.get("source_mode", "bot")

    dest_chat_id = data["dest_chat_id"]
    dest_chat_title = data.get("dest_chat_title", "")
    dest_chat_type = data.get("dest_chat_type", "channel")
    dest_topic_id = data.get("dest_topic_id")

    route_id = await RouteManager.create_route(
        user_id=user_id,
        name=name,
        source_chat_id=source_chat_id,
        source_chat_title=source_chat_title,
        source_chat_type=source_chat_type,
        source_topic_id=source_topic_id,
        source_mode=source_mode,
        dest_chat_id=dest_chat_id,
        dest_chat_title=dest_chat_title,
        dest_chat_type=dest_chat_type,
        dest_topic_id=dest_topic_id,
        forward_mode=mode
    )

    await state.clear()

    route = await RouteManager.get_route(route_id)
    text = f"""
🎉 <b>Route Created Successfully!</b> 🟢

• <b>Name:</b> {name}
• <b>Source:</b> {source_chat_title} (<code>{source_chat_id}</code>)
• <b>Destination:</b> {dest_chat_title} (<code>{dest_chat_id}</code>)
• <b>Mode:</b> {'Clean Copy 📋' if mode == 'copy' else 'Native Forward ⏩'}

Any new messages posted in the source will now be automatically routed to your destination!
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_route_details_kb(route, page=0)
    )
    await callback.answer("Route activated! 🚀")
