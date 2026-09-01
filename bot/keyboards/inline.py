from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import config

def get_main_menu_kb(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Add New Route", callback_data="wizard:start")
    )
    
    # Manage routes and stats
    builder.row(
        InlineKeyboardButton(text="📋 Manage Routes", callback_data="routes:list:0"),
        InlineKeyboardButton(text="📊 Live Stats", callback_data="menu:stats")
    )

    # If user is admin/owner, show host userbot status button
    if user_id is not None and config.is_admin(user_id):
        builder.row(
            InlineKeyboardButton(text="⚙️ Host Userbot Setup", callback_data="userbot:status"),
            InlineKeyboardButton(text="📖 User Guide", callback_data="menu:help")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="📖 User Guide & Help", callback_data="menu:help")
        )

    return builder.as_markup()


def get_userbot_status_kb(is_connected: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_connected:
        builder.row(
            InlineKeyboardButton(text="🔴 Disconnect / Logout", callback_data="userbot:logout")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🔑 Connect Host Telegram Account", callback_data="userbot:login_start")
        )
    builder.row(
        InlineKeyboardButton(text="🔄 Refresh Status", callback_data="userbot:status"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:home")
    )
    return builder.as_markup()

def get_empty_routes_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Add New Route", callback_data="wizard:start")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Back to Main Menu", callback_data="menu:home")
    )
    return builder.as_markup()

def get_help_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Add New Route", callback_data="wizard:start")
    )
    builder.row(
        InlineKeyboardButton(text="👨‍💻 Developer Info", callback_data="menu:dev_info")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Back to Main Menu", callback_data="menu:home")
    )
    return builder.as_markup()

def get_dev_info_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🚀 Make Your Own Bot",
            url="https://app.qufork.com/templates?template=tpl_1788018445033_telegram_forwarder_b"
        )
    )
    builder.row(
        InlineKeyboardButton(text="📖 Back to User Guide", callback_data="menu:help"),
        InlineKeyboardButton(text="🏠 Back to Main Menu", callback_data="menu:home")
    )
    return builder.as_markup()

def get_stats_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Add New Route", callback_data="wizard:start"),
        InlineKeyboardButton(text="🔄 Refresh Stats", callback_data="menu:stats")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Back to Main Menu", callback_data="menu:home")
    )
    return builder.as_markup()


def get_routes_list_kb(routes: List[Dict[str, Any]], page: int = 0, page_size: int = 5) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    start_idx = page * page_size
    end_idx = start_idx + page_size
    current_page_routes = routes[start_idx:end_idx]

    for r in current_page_routes:
        status_icon = "🟢" if r["is_active"] else "🔴"
        name = r["name"][:20]
        mode_icon = "📋" if r.get("forward_mode") == "copy" else "⏩"
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {mode_icon} {name}",
                callback_data=f"route:view:{r['id']}:{page}"
            )
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"routes:list:{page-1}"))
    if end_idx < len(routes):
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"routes:list:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="➕ Add New Route", callback_data="wizard:start"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:home")
    )
    return builder.as_markup()

def get_route_details_kb(route: Dict[str, Any], page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    route_id = route["id"]
    is_active = bool(route["is_active"])
    mode = route.get("forward_mode", "copy")

    toggle_text = "⏸️ Pause Route" if is_active else "▶️ Resume Route"
    mode_text = "🔄 Mode: Copy (Clone)" if mode == "copy" else "🔄 Mode: Native Forward"

    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data=f"route:toggle:{route_id}:{page}"),
        InlineKeyboardButton(text=mode_text, callback_data=f"route:mode:{route_id}:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🎯 Media & Type Filters", callback_data=f"route:filters:{route_id}:{page}"),
        InlineKeyboardButton(text="✨ Text & Customization", callback_data=f"route:custom:{route_id}:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Rename", callback_data=f"route:rename:{route_id}:{page}"),
        InlineKeyboardButton(text="🗑️ Delete Route", callback_data=f"route:delete_confirm:{route_id}:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Back to List", callback_data=f"routes:list:{page}"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:home")
    )
    return builder.as_markup()

def get_filter_settings_kb(filters: Dict[str, Any], route_id: int, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    def badge(val):
        return "✅" if val else "❌"

    builder.row(
        InlineKeyboardButton(text=f"{badge(filters.get('allow_text', 1))} 📝 Text", callback_data=f"flt:toggle:{route_id}:allow_text:{page}"),
        InlineKeyboardButton(text=f"{badge(filters.get('allow_photo', 1))} 📷 Photos", callback_data=f"flt:toggle:{route_id}:allow_photo:{page}")
    )
    builder.row(
        InlineKeyboardButton(text=f"{badge(filters.get('allow_video', 1))} 🎥 Videos", callback_data=f"flt:toggle:{route_id}:allow_video:{page}"),
        InlineKeyboardButton(text=f"{badge(filters.get('allow_document', 1))} 📁 Files", callback_data=f"flt:toggle:{route_id}:allow_document:{page}")
    )
    builder.row(
        InlineKeyboardButton(text=f"{badge(filters.get('allow_audio', 1))} 🎵 Audio", callback_data=f"flt:toggle:{route_id}:allow_audio:{page}"),
        InlineKeyboardButton(text=f"{badge(filters.get('allow_voice', 1))} 🎤 Voice", callback_data=f"flt:toggle:{route_id}:allow_voice:{page}")
    )
    builder.row(
        InlineKeyboardButton(text=f"{badge(filters.get('allow_animation', 1))} ✨ GIFs", callback_data=f"flt:toggle:{route_id}:allow_animation:{page}"),
        InlineKeyboardButton(text=f"{badge(filters.get('allow_sticker', 1))} 🎭 Stickers", callback_data=f"flt:toggle:{route_id}:allow_sticker:{page}")
    )
    builder.row(
        InlineKeyboardButton(text=f"{badge(filters.get('allow_poll', 1))} 📊 Polls", callback_data=f"flt:toggle:{route_id}:allow_poll:{page}"),
        InlineKeyboardButton(text=f"{badge(filters.get('remove_links', 0))} 🔗 Strip Links", callback_data=f"flt:toggle:{route_id}:remove_links:{page}")
    )
    builder.row(
        InlineKeyboardButton(text=f"{badge(filters.get('remove_usernames', 0))} 👤 Strip Usernames", callback_data=f"flt:toggle:{route_id}:remove_usernames:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Route", callback_data=f"route:view:{route_id}:{page}")
    )
    return builder.as_markup()

def get_customization_kb(customs: Dict[str, Any], route_id: int, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    header_status = "✅ Set" if (customs.get("header_text") or "").strip() else "❌ None"
    footer_status = "✅ Set" if (customs.get("footer_text") or "").strip() else "❌ None"
    pin_status = "✅ Yes" if customs.get("pin_message", 0) else "❌ No"
    prot_status = "✅ Yes" if customs.get("protect_content", 0) else "❌ No"

    builder.row(
        InlineKeyboardButton(text=f"🔤 Header ({header_status})", callback_data=f"cust:header:{route_id}:{page}"),
        InlineKeyboardButton(text=f"🔤 Footer ({footer_status})", callback_data=f"cust:footer:{route_id}:{page}")
    )
    builder.row(
        InlineKeyboardButton(text=f"📌 Pin Sent ({pin_status})", callback_data=f"cust:toggle:{route_id}:pin_message:{page}"),
        InlineKeyboardButton(text=f"🔒 Protect Copy ({prot_status})", callback_data=f"cust:toggle:{route_id}:protect_content:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🏷️ Keyword Whitelist/Blacklist", callback_data=f"cust:keywords:{route_id}:{page}"),
        InlineKeyboardButton(text="🔀 Text Replacements", callback_data=f"cust:replacements:{route_id}:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Route", callback_data=f"route:view:{route_id}:{page}")
    )
    return builder.as_markup()

def get_replacements_kb(replacements: List[Dict[str, Any]], route_id: int, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for rep in replacements:
        find_txt = rep["find_text"][:12]
        rep_txt = rep["replace_text"][:12]
        builder.row(
            InlineKeyboardButton(
                text=f"❌ '{find_txt}' ➔ '{rep_txt}'",
                callback_data=f"rep:del:{rep['id']}:{route_id}:{page}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Add New Replacement", callback_data=f"rep:add:{route_id}:{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Customizations", callback_data=f"route:custom:{route_id}:{page}")
    )
    return builder.as_markup()

def get_confirm_delete_kb(route_id: int, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑️ YES, DELETE", callback_data=f"route:delete_do:{route_id}:{page}"),
        InlineKeyboardButton(text="❌ CANCEL", callback_data=f"route:view:{route_id}:{page}")
    )
    return builder.as_markup()

def get_forward_mode_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Clean Copy (No 'Forwarded from' header)", callback_data="wiz:mode:copy")
    )
    builder.row(
        InlineKeyboardButton(text="⏩ Native Forward (Keep original header)", callback_data="wiz:mode:forward")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Cancel", callback_data="wizard:cancel")
    )
    return builder.as_markup()

def get_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Cancel Operation", callback_data="wizard:cancel"))
    return builder.as_markup()

def get_skip_cancel_kb(action_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭️ Skip / Leave Empty", callback_data=f"{action_prefix}:skip"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="wizard:cancel")
    )
    return builder.as_markup()

def get_force_sub_kb(unjoined_channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Builds the inline keyboard for Force Subscribe screen.
    Includes direct join links for all unjoined channels and a final verification button.
    """
    builder = InlineKeyboardBuilder()

    for idx, ch in enumerate(unjoined_channels, 1):
        btn_text = ch.get("title") or f"📢 Join Channel {idx}"
        url = ch.get("url")
        if url:
            builder.row(InlineKeyboardButton(text=f"👉 Join {btn_text}", url=url))
        else:
            # Fallback if only chat_id is present
            chat_id = ch.get("chat_id")
            builder.row(InlineKeyboardButton(text=f"👉 Channel {idx} ({chat_id})", callback_data="fsub:verify"))

    # The last button to verify joining
    builder.row(
        InlineKeyboardButton(text="🔄 I Have Joined (Verify)", callback_data="fsub:verify")
    )
    return builder.as_markup()

