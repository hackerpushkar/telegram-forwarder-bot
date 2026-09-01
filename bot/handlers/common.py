import time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from bot.keyboards.inline import (
    get_main_menu_kb,
    get_force_sub_kb,
    get_help_kb,
    get_dev_info_kb,
    get_stats_kb
)
from bot.database.models import StatsManager, RouteManager
from bot.config import config
from bot.services.force_sub import check_force_sub

router = Router(name="common_router")

# Developer & Updates Configuration (easily editable)
DEVELOPER_USERNAME = "@pushkarsingh1586"
UPDATE_CHANNEL_URL = "https://t.me/QuFork"
UPDATE_CHANNEL_NAME = "Update Channel"
CREATE_BOT_URL = "https://app.qufork.com/templates?template=tpl_1788018445033_telegram_forwarder_b"


async def get_owner_display(bot) -> str:
    """Helper to fetch and format bot owner/admin usernames and IDs."""
    if not config.ADMIN_IDS:
        return "<i>Not Configured</i>"
    
    owners = []
    for admin_id in config.ADMIN_IDS:
        try:
            chat = await bot.get_chat(admin_id)
            if chat.username:
                owners.append(f"@{chat.username} (<code>{admin_id}</code>)")
            elif chat.first_name:
                full_name = chat.first_name + (f" {chat.last_name}" if chat.last_name else "")
                owners.append(f"<a href=\"tg://user?id={admin_id}\">{full_name}</a> (<code>{admin_id}</code>)")
            else:
                owners.append(f"<code>{admin_id}</code>")
        except Exception:
            owners.append(f"<code>{admin_id}</code>")
    return ", ".join(owners)

FORCE_SUB_TEXT = """
👋 <b>Welcome!</b>

⚠️ <b>To use this bot, you must join our official channel(s) first.</b>

Please click the button(s) below to join all channels, then tap <b>'🔄 I Have Joined (Verify)'</b> to continue!
"""

START_TEXT = """
🚀 <b>Welcome to Super Telegram Forwarder Bot!</b>

Your all-in-one message routing engine for Telegram. Forward messages seamlessly across:
• 📢 <b>Channel ➔ Channel</b>
• 👥 <b>Group ➔ Channel</b>
• 📢 <b>Channel ➔ Group</b>
• 👥 <b>Group ➔ Group</b> <i>(including Forum Topics)</i>

✨ <b>Super Features:</b>
• 🧼 <b>Clean Copy (Clone):</b> Strips the "Forwarded from" tag so messages look 100% native.
• ⏩ <b>Native Forward:</b> Preserves original sender/channel credits.
• 🖼️ <b>Media Group (Album) Batching:</b> Keeps multi-photo albums grouped.
• 🎯 <b>Custom Filters:</b> Filter by Media Type (Photos, Videos, Files, Audio, etc.).
• 🏷️ <b>Smart Keywords:</b> Whitelist / Blacklist keyword and regex filtering.
• 🔤 <b>Watermarks & Branding:</b> Automatic Header & Footer injection.
• 🔀 <b>Find & Replace:</b> Swap affiliate links, remove tags or usernames.
• 🛡️ <b>Anti-Flood System:</b> Automatic rate-limit handling and backoff.

👇 <i>Click a button below or type <code>/help</code> to get started:</i>
"""


HELP_TEXT = """
📖 <b>Super Telegram Forwarder Bot — Setup Guide</b>

<b>1️⃣ Setup Permissions</b>
• <b>Source Channel/Group:</b>
  Add this bot as an <b>Administrator</b> (or member if group privacy mode is disabled in @BotFather) so it can see incoming posts.
• <b>Destination Channel/Group:</b>
  Add this bot as an <b>Administrator</b> with <b>Post Messages / Send Messages</b> permission.

<b>2️⃣ Find Your Chat IDs</b>
• For public channels/groups: You can simply use <code>@channel_username</code>.
• For private channels/groups:
  1. Forward any message from the private channel/group to <code>@userinfobot</code> or <code>@JsonDumpBot</code>.
  2. The ID usually starts with <code>-100...</code> (e.g. <code>-1001234567890</code>).
  3. You can also simply forward a message directly to this bot during the setup wizard!

<b>3️⃣ Useful Commands</b>
• <code>/start</code> — Open main control dashboard
• <code>/newroute</code> — Start interactive wizard to create a forward route
• <code>/routes</code> — View and manage existing routes
• <code>/stats</code> — View bot throughput and live stats
• <code>/ping</code> — Health and latency check
• <code>/help</code> — Show this guide

<b>4️⃣ Tips</b>
• You can toggle individual media types (Photos, Videos, Voice, etc.) in Route Settings.
• You can add custom Headers and Footers to auto-brand posts.
• You can configure Word/Link replacements to swap affiliate tags.
"""

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id if message.from_user else None
    
    # Force Subscribe Verification Check
    if user_id is not None and message.bot:
        is_sub, unjoined = await check_force_sub(message.bot, user_id)
        if not is_sub:
            await message.answer(
                text=FORCE_SUB_TEXT,
                parse_mode="HTML",
                reply_markup=get_force_sub_kb(unjoined)
            )
            return

    await message.answer(
        text=START_TEXT,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(user_id)
    )

@router.callback_query(F.data == "fsub:verify")
async def cb_fsub_verify(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else None
    if not user_id or not callback.bot:
        await callback.answer("Error checking status.", show_alert=True)
        return

    is_sub, unjoined = await check_force_sub(callback.bot, user_id)
    if is_sub:
        await callback.answer("✅ Thank you for joining! Access granted.", show_alert=True)
        if callback.message:
            await callback.message.edit_text(
                text=START_TEXT,
                parse_mode="HTML",
                reply_markup=get_main_menu_kb(user_id)
            )
    else:
        remaining_count = len(unjoined)
        await callback.answer(
            f"❌ You have not joined all required channels yet! ({remaining_count} remaining). Please join and verify again.",
            show_alert=True
        )
        if callback.message:
            try:
                await callback.message.edit_reply_markup(
                    reply_markup=get_force_sub_kb(unjoined)
                )
            except Exception:
                pass


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        text=HELP_TEXT,
        parse_mode="HTML",
        reply_markup=get_help_kb()
    )

@router.message(Command("ping"))
async def cmd_ping(message: Message):
    start_t = time.perf_counter()
    msg = await message.answer("🏓 <i>Pinging Telegram API...</i>", parse_mode="HTML")
    latency_ms = (time.perf_counter() - start_t) * 1000
    await msg.edit_text(
        f"🏓 <b>Pong!</b>\n\n"
        f"⚡ <b>API Latency:</b> <code>{latency_ms:.1f} ms</code>\n"
        f"🤖 <b>Bot Status:</b> 🟢 Online & Healthy\n"
        f"🛡️ <b>Engine:</b> Super Forwarder v1.0",
        parse_mode="HTML"
    )

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    stats = await StatsManager.get_all()
    all_routes = await RouteManager.get_all_routes()
    active_routes = [r for r in all_routes if r["is_active"]]

    text = f"""
📊 <b>Bot Performance & Statistics</b>

• <b>Total Messages Forwarded:</b> <code>{stats.get('total_forwarded', 0):,}</code>
• <b>Filtered / Skipped Messages:</b> <code>{stats.get('total_filtered', 0):,}</code>
• <b>Encountered Errors:</b> <code>{stats.get('total_errors', 0):,}</code>

• <b>Total Configured Routes:</b> <code>{len(all_routes)}</code>
• <b>Active Routes:</b> <code>{len(active_routes)} 🟢</code>
• <b>Paused Routes:</b> <code>{len(all_routes) - len(active_routes)} 🔴</code>
"""
    await message.answer(text=text, parse_mode="HTML", reply_markup=get_stats_kb())

@router.callback_query(F.data == "menu:home")
async def cb_home(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else None
    await callback.message.edit_text(
        text=START_TEXT,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(user_id)
    )
    await callback.answer()

@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery):
    await callback.message.edit_text(
        text=HELP_TEXT,
        parse_mode="HTML",
        reply_markup=get_help_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "menu:stats")
async def cb_stats(callback: CallbackQuery):
    stats = await StatsManager.get_all()
    all_routes = await RouteManager.get_all_routes()
    active_routes = [r for r in all_routes if r["is_active"]]

    text = f"""
📊 <b>Bot Performance & Statistics</b>

• <b>Total Messages Forwarded:</b> <code>{stats.get('total_forwarded', 0):,}</code>
• <b>Filtered / Skipped Messages:</b> <code>{stats.get('total_filtered', 0):,}</code>
• <b>Encountered Errors:</b> <code>{stats.get('total_errors', 0):,}</code>

• <b>Total Configured Routes:</b> <code>{len(all_routes)}</code>
• <b>Active Routes:</b> <code>{len(active_routes)} 🟢</code>
• <b>Paused Routes:</b> <code>{len(all_routes) - len(active_routes)} 🔴</code>
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_stats_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "menu:dev_info")
async def cb_dev_info(callback: CallbackQuery):
    owner_str = await get_owner_display(callback.bot) if callback.bot else "<code>" + ", ".join(map(str, config.ADMIN_IDS)) + "</code>"
    
    dev_text = (
        f"👨‍💻 <b>Developer & Bot Information</b>\n\n"
        f"• <b>Developer:</b> {DEVELOPER_USERNAME}\n"
        f"• <b>Owner:</b> {owner_str}\n"
        f"• <b>Bots Update Join:</b> <a href=\"{UPDATE_CHANNEL_URL}\">{UPDATE_CHANNEL_URL}</a>\n\n"
        f"ℹ️ <b>More Information:</b>\n"
        f"• <b>Engine:</b> Super Telegram Forwarder v1.0\n"
        f"• <b>Modes:</b> Clean Copy (Clone), Native Forward, Multi-Media Batching\n"
        f"• <b>Filtering:</b> Custom Media Filters, Keyword Whitelist/Blacklist, Regex Replacements\n"
        f"• <b>Dual Core:</b> Bot API & MTProto Userbot support for private and restricted chats\n\n"
        f"⚡ <i>Want to build and deploy your own instance of this bot? Click below!</i>"
    )
    
    await callback.message.edit_text(
        text=dev_text,
        parse_mode="HTML",
        reply_markup=get_dev_info_kb(),
        disable_web_page_preview=True
    )
    await callback.answer()


