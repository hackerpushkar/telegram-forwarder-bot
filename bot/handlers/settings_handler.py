from typing import Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards.inline import (
    get_filter_settings_kb,
    get_customization_kb,
    get_replacements_kb,
    get_cancel_kb,
    get_skip_cancel_kb,
    get_route_details_kb
)
from bot.database.models import RouteManager
from bot.config import config

router = Router(name="settings_router")

def can_access_route(route: Optional[dict], user_id: Optional[int]) -> bool:
    if not route or user_id is None:
        return False
    if route.get("user_id") == user_id:
        return True
    return config.is_admin(user_id)

class HeaderFooterState(StatesGroup):
    route_id = State()
    page = State()
    target = State()  # 'header' or 'footer'
    text = State()

class KeywordsState(StatesGroup):
    route_id = State()
    page = State()
    target = State()  # 'whitelist' or 'blacklist'
    keywords = State()

class AddReplacementState(StatesGroup):
    route_id = State()
    page = State()
    find_text = State()
    replace_text = State()
    is_regex = State()

# --- Filter Settings ---

@router.callback_query(F.data.startswith("route:filters:"))
async def cb_route_filters(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    filters = await RouteManager.get_filters(route_id)
    text = f"""
🎯 <b>Media & Content Filters for '{route['name']}'</b>

Click any button to toggle allowed media types or content cleanup options:
• ✅ = <b>Allowed / Active</b>
• ❌ = <b>Blocked / Disabled</b>
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_filter_settings_kb(filters or {}, route_id=route_id, page=page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("flt:toggle:"))
async def cb_filter_toggle(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    column = parts[3]
    page = int(parts[4]) if len(parts) > 4 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    await RouteManager.toggle_filter_option(route_id, column)
    filters = await RouteManager.get_filters(route_id)


    text = f"""
🎯 <b>Media & Content Filters for Route #{route_id}</b>

Click any button to toggle allowed media types or content cleanup options:
• ✅ = <b>Allowed / Active</b>
• ❌ = <b>Blocked / Disabled</b>
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_filter_settings_kb(filters or {}, route_id=route_id, page=page)
    )
    await callback.answer("Filter updated!")

# --- Customization Menu ---

@router.callback_query(F.data.startswith("route:custom:"))
async def cb_route_custom(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    customs = await RouteManager.get_customizations(route_id) or {}
    filters = await RouteManager.get_filters(route_id) or {}

    header_disp = customs.get("header_text") or "<i>None</i>"
    footer_disp = customs.get("footer_text") or "<i>None</i>"
    wl_disp = filters.get("keyword_whitelist") or "<i>None</i>"
    bl_disp = filters.get("keyword_blacklist") or "<i>None</i>"

    text = f"""
✨ <b>Customization & Text Engine for '{route['name']}'</b>

• <b>Header Text:</b> {header_disp}
• <b>Footer Text:</b> {footer_disp}
• <b>Keyword Whitelist:</b> {wl_disp}
• <b>Keyword Blacklist:</b> {bl_disp}

<i>Click an option below to modify branding or keywords:</i>
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_customization_kb(customs, route_id=route_id, page=page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cust:toggle:"))
async def cb_custom_toggle(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    field = parts[3]
    page = int(parts[4]) if len(parts) > 4 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    customs = await RouteManager.get_customizations(route_id) or {}
    curr_val = customs.get(field, 0)
    new_val = 1 - curr_val

    if field == "pin_message":
        await RouteManager.update_customizations(route_id, pin_message=new_val)
    elif field == "protect_content":
        await RouteManager.update_customizations(route_id, protect_content=new_val)

    await cb_route_custom(callback)

# --- Header & Footer Configuration ---

@router.callback_query(F.data.startswith("cust:header:") | F.data.startswith("cust:footer:"))
async def cb_set_header_footer(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    target = parts[0].split(":")[0].replace("cust", "")  # "header" or "footer"
    target = "header" if "header" in parts[0] else "footer"
    route_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    await state.set_state(HeaderFooterState.text)
    await state.update_data(route_id=route_id, page=page, target=target)

    text = f"""
🔤 <b>Set Custom {target.upper()} Text</b>

Send the text you want to automatically prepend (for Header) or append (for Footer) to every forwarded message.
Supports emojis, links, and hashtags!

• Send <code>clear</code> or <code>none</code> to remove.
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )
    await callback.answer()

@router.message(HeaderFooterState.text)
async def process_header_footer_text(message: Message, state: FSMContext):
    data = await state.get_data()
    route_id = data["route_id"]
    page = data["page"]
    target = data["target"]
    user_id = message.from_user.id if message.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await message.answer("⛔ Access Denied: You do not have permission to modify this route.")
        await state.clear()
        return

    raw_text = message.text or ""
    final_text = "" if raw_text.strip().lower() in ["clear", "none", "remove"] else raw_text.strip()

    if target == "header":
        await RouteManager.update_customizations(route_id, header_text=final_text)
    else:
        await RouteManager.update_customizations(route_id, footer_text=final_text)

    await state.clear()
    await message.answer(
        f"✅ <b>{target.capitalize()} updated successfully!</b>",
        parse_mode="HTML"
    )

    customs = await RouteManager.get_customizations(route_id) or {}
    await message.answer(
        text="Customization Menu:",
        reply_markup=get_customization_kb(customs, route_id=route_id, page=page)
    )

# --- Keywords Configuration ---

@router.callback_query(F.data.startswith("cust:keywords:"))
async def cb_keywords_menu(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    await state.set_state(KeywordsState.keywords)
    await state.update_data(route_id=route_id, page=page)

    filters = await RouteManager.get_filters(route_id) or {}

    text = f"""
🏷️ <b>Smart Keyword Filtering</b>

• <b>Current Whitelist:</b> <code>{filters.get('keyword_whitelist') or 'None'}</code>
• <b>Current Blacklist:</b> <code>{filters.get('keyword_blacklist') or 'None'}</code>

To update, send your keywords in this format:
<code>blacklist: spam, scam, crypto promo, @adbot</code>
or
<code>whitelist: breaking news, alert, discount</code>
or send <code>clear all</code> to remove all keyword filters.
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )
    await callback.answer()

@router.message(KeywordsState.keywords)
async def process_keywords(message: Message, state: FSMContext):
    data = await state.get_data()
    route_id = data["route_id"]
    page = data["page"]
    user_id = message.from_user.id if message.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await message.answer("⛔ Access Denied: You do not have permission to modify this route.")
        await state.clear()
        return

    raw_text = message.text.strip() if message.text else ""

    if raw_text.lower() in ["clear", "clear all", "none"]:
        await RouteManager.update_keywords(route_id, whitelist="", blacklist="")
        await message.answer("✅ Cleared all keyword filters!")
    elif raw_text.lower().startswith("blacklist:"):
        kw = raw_text[len("blacklist:"):].strip()
        await RouteManager.update_keywords(route_id, blacklist=kw)
        await message.answer(f"✅ Blacklist updated: <code>{kw}</code>", parse_mode="HTML")
    elif raw_text.lower().startswith("whitelist:"):
        kw = raw_text[len("whitelist:"):].strip()
        await RouteManager.update_keywords(route_id, whitelist=kw)
        await message.answer(f"✅ Whitelist updated: <code>{kw}</code>", parse_mode="HTML")
    else:
        # Default to blacklist if no prefix specified
        await RouteManager.update_keywords(route_id, blacklist=raw_text)
        await message.answer(f"✅ Blacklist set to: <code>{raw_text}</code>", parse_mode="HTML")

    await state.clear()
    customs = await RouteManager.get_customizations(route_id) or {}
    await message.answer(
        text="Customization Menu:",
        reply_markup=get_customization_kb(customs, route_id=route_id, page=page)
    )

# --- Text Replacements ---

@router.callback_query(F.data.startswith("cust:replacements:"))
async def cb_replacements_menu(callback: CallbackQuery):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    replacements = await RouteManager.get_replacements(route_id)
    text = f"""
🔀 <b>Word & Link Replacements for Route #{route_id}</b>

Replace text, affiliate tags, or sponsor links automatically before forwarding.
Click an entry below to delete it, or click <b>'➕ Add New Replacement'</b>:
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_replacements_kb(replacements, route_id=route_id, page=page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rep:del:"))
async def cb_rep_delete(callback: CallbackQuery):
    parts = callback.data.split(":")
    rep_id = int(parts[2])
    route_id = int(parts[3])
    page = int(parts[4]) if len(parts) > 4 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    await RouteManager.delete_replacement(rep_id)
    await callback.answer("Replacement removed! 🗑️")

    replacements = await RouteManager.get_replacements(route_id)
    text = f"""
🔀 <b>Word & Link Replacements for Route #{route_id}</b>

Replace text, affiliate tags, or sponsor links automatically before forwarding.
Click an entry below to delete it, or click <b>'➕ Add New Replacement'</b>:
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_replacements_kb(replacements, route_id=route_id, page=page)
    )

@router.callback_query(F.data.startswith("rep:add:"))
async def cb_rep_add(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    route_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    user_id = callback.from_user.id if callback.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await callback.answer("⛔ Access Denied: You cannot modify this route.", show_alert=True)
        return

    await state.set_state(AddReplacementState.find_text)
    await state.update_data(route_id=route_id, page=page)

    text = """
🔀 <b>Step 1/2: Enter text to FIND</b>

Send the word, phrase, link, or username you want to replace:
<i>(Example: <code>@OldChannel</code> or <code>https://oldlink.com</code>)</i>
"""
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )
    await callback.answer()

@router.message(AddReplacementState.find_text)
async def process_rep_find(message: Message, state: FSMContext):
    find_text = message.text.strip() if message.text else ""
    if not find_text:
        await message.answer("⚠️ Please provide a non-empty text to find:")
        return

    await state.update_data(find_text=find_text)
    await state.set_state(AddReplacementState.replace_text)

    text = f"""
🔀 <b>Step 2/2: Enter REPLACEMENT text</b>
Finding: <code>{find_text}</code>

Send the new text to replace it with:
<i>(Send <code>empty</code> or <code>remove</code> to completely delete the matched text)</i>
"""
    await message.answer(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())

@router.message(AddReplacementState.replace_text)
async def process_rep_replace(message: Message, state: FSMContext):
    replace_text = message.text.strip() if message.text else ""
    if replace_text.lower() in ["empty", "remove", "none", "delete"]:
        replace_text = ""

    data = await state.get_data()
    route_id = data["route_id"]
    page = data["page"]
    find_text = data["find_text"]
    user_id = message.from_user.id if message.from_user else 0

    route = await RouteManager.get_route(route_id)
    if not route or not can_access_route(route, user_id):
        await message.answer("⛔ Access Denied: You do not have permission to modify this route.")
        await state.clear()
        return

    await RouteManager.add_replacement(route_id, find_text=find_text, replace_text=replace_text)
    await state.clear()

    await message.answer(
        f"✅ Replacement added: <code>'{find_text}'</code> ➔ <code>'{replace_text}'</code>",
        parse_mode="HTML"
    )

    replacements = await RouteManager.get_replacements(route_id)
    await message.answer(
        text="Replacements List:",
        reply_markup=get_replacements_kb(replacements, route_id=route_id, page=page)
    )

