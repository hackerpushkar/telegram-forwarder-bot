import time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from bot.keyboards.inline import get_main_menu_kb
from bot.database.models import StatsManager, RouteManager
from bot.config import config

router = Router(name="common_router")

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
    await message.answer(
        text=START_TEXT,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(user_id)
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    user_id = message.from_user.id if message.from_user else None
    await message.answer(
        text=HELP_TEXT,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(user_id)
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
    await message.answer(text=text, parse_mode="HTML", reply_markup=get_main_menu_kb())

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
    user_id = callback.from_user.id if callback.from_user else None
    await callback.message.edit_text(
        text=HELP_TEXT,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(user_id)
    )
    await callback.answer()

@router.callback_query(F.data == "menu:stats")
async def cb_stats(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else None
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
        reply_markup=get_main_menu_kb(user_id)
    )
    await callback.answer()
