from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards.inline import get_userbot_status_kb, get_cancel_kb, get_main_menu_kb
from bot.services.userbot import userbot_manager
from bot.config import config

router = Router(name="userbot_router")

class UserbotLoginState(StatesGroup):
    phone = State()
    code = State()
    password = State()

@router.message(Command("userbot"))
@router.callback_query(F.data == "userbot:status")
async def show_userbot_status(event):
    user_id = event.from_user.id if event.from_user else 0
    if not config.is_admin(user_id):
        if isinstance(event, CallbackQuery):
            await event.answer("⛔ Access Denied: Only bot administrators can use /userbot.", show_alert=True)
        else:
            await event.answer("⛔ <b>Access Denied:</b> Only bot administrators can configure the Host Userbot.", parse_mode="HTML")
        return

    is_conn = userbot_manager.is_connected()
    me = await userbot_manager.get_me() if is_conn else None

    if is_conn and me:
        name = f"{me.get('first_name') or ''} {me.get('last_name') or ''}".strip()
        username = f"@{me.get('username')}" if me.get('username') else 'None'
        phone = me.get('phone') or 'Hidden'
        status_text = f"""
👤 <b>Telegram Userbot Status: 🟢 CONNECTED</b>

• <b>Account:</b> {name}
• <b>Username:</b> {username}
• <b>Phone:</b> <code>+{phone}</code>
• <b>User ID:</b> <code>{me.get('id')}</code>

<i>✨ Host Userbot is active! It will automatically join other people's channels/groups in the background and forward new messages to users' destination channels.</i>
"""
    else:
        status_text = f"""
👤 <b>Telegram Userbot Status: 🔴 DISCONNECTED</b>

<b>Why connect the Host Userbot?</b>
When users create forwarding routes for <b>public or other people's channels/groups</b> where they cannot add a bot, the Host Userbot automatically joins them and reads posts for them.

<b>Setup Requirements:</b>
1. Ensure <code>API_ID</code> and <code>API_HASH</code> are set in <code>.env</code> from https://my.telegram.org
2. Click <b>'🔑 Connect Host Telegram Account'</b> below to log in with your phone number and OTP code.
"""

    kb = get_userbot_status_kb(is_conn)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text=status_text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text=status_text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "userbot:login_start")
async def start_userbot_login(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else 0
    if not config.is_admin(user_id):
        await callback.answer("⛔ Access Denied: Only administrators can log in the Userbot.", show_alert=True)
        return

    if not config.API_ID or not config.API_HASH:
        await callback.answer(
            "⚠️ API_ID and API_HASH are missing in .env! Please set them first from my.telegram.org.",
            show_alert=True
        )
        return

    await state.clear()
    await state.set_state(UserbotLoginState.phone)

    text = """
🔑 <b>Host Userbot Login — Step 1/3: Enter Phone Number</b>

Please enter your Telegram phone number with international country code:
<i>(Example: <code>+1234567890</code> or <code>+919876543210</code>)</i>
"""
    await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())
    await callback.answer()

@router.message(UserbotLoginState.phone)
async def process_userbot_phone(message: Message, state: FSMContext):
    user_id = message.from_user.id if message.from_user else 0
    if not config.is_admin(user_id):
        await message.answer("⛔ Access Denied.")
        await state.clear()
        return

    phone = message.text.strip() if message.text else ""
    if not phone.startswith("+") and not phone.isdigit():
        await message.answer("⚠️ Please enter a valid phone number starting with '+' and your country code (e.g. <code>+1234567890</code>):", parse_mode="HTML")
        return

    wait_msg = await message.answer("⏳ <i>Requesting Telegram verification code...</i>", parse_mode="HTML")
    success, resp_msg = await userbot_manager.send_login_code(phone)

    if not success:
        await wait_msg.edit_text(
            f"❌ <b>Failed to send verification code:</b>\n{resp_msg}",
            parse_mode="HTML",
            reply_markup=get_cancel_kb()
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(UserbotLoginState.code)

    text = f"""
📲 <b>Host Userbot Login — Step 2/3: Enter Verification Code</b>

A code was sent to your Telegram app (or SMS) for <code>{phone}</code>.
Please enter the code below:
<i>(If your code is 12345, you can send <code>1 2 3 4 5</code> or <code>12345</code>)</i>
"""
    await wait_msg.edit_text(text=text, parse_mode="HTML", reply_markup=get_cancel_kb())

@router.message(UserbotLoginState.code)
async def process_userbot_code(message: Message, state: FSMContext):
    user_id = message.from_user.id if message.from_user else 0
    if not config.is_admin(user_id):
        await message.answer("⛔ Access Denied.")
        await state.clear()
        return

    code = message.text.strip() if message.text else ""
    wait_msg = await message.answer("⏳ <i>Verifying code...</i>", parse_mode="HTML")

    success, resp_msg = await userbot_manager.sign_in_with_code(code)

    if not success:
        if resp_msg == "2FA_REQUIRED":
            await state.update_data(code=code)
            await state.set_state(UserbotLoginState.password)
            await wait_msg.edit_text(
                "🔒 <b>Two-Step Verification (2FA) Password Required</b>\n\n"
                "Your Telegram account has a 2FA cloud password enabled.\n"
                "Please enter your 2FA password below:",
                parse_mode="HTML",
                reply_markup=get_cancel_kb()
            )
            return
        else:
            await wait_msg.edit_text(
                f"❌ <b>Sign-in Failed:</b>\n{resp_msg}\n\nPlease check the code and try again:",
                parse_mode="HTML",
                reply_markup=get_cancel_kb()
            )
            return

    await state.clear()
    await wait_msg.edit_text(
        f"🎉 <b>Host Userbot Connected Successfully!</b> 🟢\n\n{resp_msg}",
        parse_mode="HTML",
        reply_markup=get_userbot_status_kb(True)
    )

@router.message(UserbotLoginState.password)
async def process_userbot_password(message: Message, state: FSMContext):
    user_id = message.from_user.id if message.from_user else 0
    if not config.is_admin(user_id):
        await message.answer("⛔ Access Denied.")
        await state.clear()
        return

    password = message.text.strip() if message.text else ""
    data = await state.get_data()
    code = data.get("code", "")

    wait_msg = await message.answer("⏳ <i>Verifying 2FA password...</i>", parse_mode="HTML")
    success, resp_msg = await userbot_manager.sign_in_with_code(code, password=password)

    if not success:
        await wait_msg.edit_text(
            f"❌ <b>2FA Verification Failed:</b>\n{resp_msg}\n\nPlease enter the correct password:",
            parse_mode="HTML",
            reply_markup=get_cancel_kb()
        )
        return

    await state.clear()
    await wait_msg.edit_text(
        f"🎉 <b>Host Userbot Connected Successfully!</b> 🟢\n\n{resp_msg}",
        parse_mode="HTML",
        reply_markup=get_userbot_status_kb(True)
    )

@router.callback_query(F.data == "userbot:logout")
async def process_userbot_logout(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    if not config.is_admin(user_id):
        await callback.answer("⛔ Access Denied: Only administrators can log out the Userbot.", show_alert=True)
        return

    success, msg = await userbot_manager.logout()
    await callback.answer(msg, show_alert=True)
    await show_userbot_status(callback)
