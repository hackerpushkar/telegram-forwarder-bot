import os
import uuid
import unittest
from pathlib import Path

test_id = uuid.uuid4().hex[:8]
TEST_DB_PATH = f"data/test_{test_id}.db"
os.environ["DB_PATH"] = TEST_DB_PATH
os.environ["BOT_TOKEN"] = "123456:TEST_TOKEN_FAKE"
os.environ["ADMIN_IDS"] = "123456789,987654321"
os.environ["API_ID"] = "123456"
os.environ["API_HASH"] = "abcdef123456"

from bot.config import config

config.DB_PATH = TEST_DB_PATH
config.ADMIN_IDS = [123456789, 987654321]
config.API_ID = 123456
config.API_HASH = "abcdef123456"



from bot.database.db import init_db, get_db
from bot.database.models import RouteManager, StatsManager, UserbotAuthManager
from bot.services.transformer import MessageTransformer
from bot.handlers import get_main_router

class DummyMessage:
    def __init__(self, text=None, caption=None, content_type="text"):
        self.text = text
        self.caption = caption
        self.photo = [1] if content_type == "photo" else None
        self.video = 1 if content_type == "video" else None
        self.document = 1 if content_type == "document" else None
        self.audio = 1 if content_type == "audio" else None
        self.voice = 1 if content_type == "voice" else None
        self.animation = 1 if content_type == "animation" else None
        self.sticker = 1 if content_type == "sticker" else None
        self.poll = 1 if content_type == "poll" else None
        self.video_note = None
        self.contact = None
        self.location = None

class TestForwarderCore(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        Path("data").mkdir(parents=True, exist_ok=True)
        config.ADMIN_IDS = [123456789, 987654321]



    async def asyncSetUp(self):
        await init_db()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

    def test_config_parsing(self):
        self.assertIn(123456789, config.ADMIN_IDS)
        self.assertIn(987654321, config.ADMIN_IDS)
        self.assertTrue(config.is_admin(123456789))
        self.assertFalse(config.is_admin(999999999))
        self.assertEqual(config.API_ID, 123456)
        self.assertEqual(config.API_HASH, "abcdef123456")

        # Test single integer ADMIN_IDS
        cfg_single = config.__class__(BOT_TOKEN="fake", ADMIN_IDS=6367495275)
        self.assertEqual(cfg_single.ADMIN_IDS, [6367495275])

        # Test comma-separated string ADMIN_IDS
        cfg_str = config.__class__(BOT_TOKEN="fake", ADMIN_IDS="6367495275, 111222333")
        self.assertEqual(cfg_str.ADMIN_IDS, [6367495275, 111222333])

        # Test MongoDB Config
        cfg_mongo = config.__class__(BOT_TOKEN="fake", MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net/testdb")
        self.assertEqual(cfg_mongo.MONGO_URI, "mongodb+srv://user:pass@cluster.mongodb.net/testdb")
        self.assertEqual(cfg_mongo.MONGO_DB_NAME, "forwarder_bot")

        # Test ADMINS_ONLY boolean parsing with trailing/leading spaces
        cfg_bool_f = config.__class__(BOT_TOKEN="fake", ADMINS_ONLY="false ")
        self.assertFalse(cfg_bool_f.ADMINS_ONLY)
        cfg_bool_t = config.__class__(BOT_TOKEN="fake", ADMINS_ONLY=" true")
        self.assertTrue(cfg_bool_t.ADMINS_ONLY)

    async def test_database_crud(self):
        # 1. Create Route in Bot Mode
        route_id = await RouteManager.create_route(
            user_id=123456789,
            name="Test Crypto Route",
            source_chat_id=-100111222333,
            source_chat_title="Source Channel",
            source_chat_type="channel",
            dest_chat_id=-100444555666,
            dest_chat_title="Dest Group",
            dest_chat_type="supergroup",
            forward_mode="copy",
            source_mode="bot"
        )
        self.assertIsInstance(route_id, int)

        # 2. Get Route
        route = await RouteManager.get_route(route_id)
        self.assertIsNotNone(route)
        self.assertEqual(route["name"], "Test Crypto Route")
        self.assertEqual(route["source_chat_id"], -100111222333)
        self.assertEqual(route["dest_chat_id"], -100444555666)
        self.assertEqual(route["forward_mode"], "copy")
        self.assertEqual(route["source_mode"], "bot")
        self.assertEqual(route["is_active"], 1)

        # 3. Create Route in Userbot Mode
        ub_route_id = await RouteManager.create_route(
            user_id=123456789,
            name="Public Signal Route",
            source_chat_id=-100777888999,
            source_chat_title="Other Public Signals",
            source_chat_type="channel",
            dest_chat_id=-100444555666,
            dest_chat_title="Dest Group",
            dest_chat_type="supergroup",
            forward_mode="copy",
            source_mode="userbot"
        )
        ub_route = await RouteManager.get_route(ub_route_id)
        self.assertEqual(ub_route["source_mode"], "userbot")

        # 4. Get Active Routes by source and mode
        bot_routes = await RouteManager.get_active_routes_for_source(-100111222333, source_mode="bot")
        self.assertEqual(len(bot_routes), 1)

        ub_routes = await RouteManager.get_active_routes_for_source(-100777888999, source_mode="userbot")
        self.assertEqual(len(ub_routes), 1)

        # 5. Userbot Auth Manager
        await UserbotAuthManager.save_session_string("dummy_session_string_abc123")
        saved_session = await UserbotAuthManager.get_session_string()
        self.assertEqual(saved_session, "dummy_session_string_abc123")
        await UserbotAuthManager.clear_session()
        self.assertIsNone(await UserbotAuthManager.get_session_string())

        # Clean up
        await RouteManager.delete_route(route_id)
        await RouteManager.delete_route(ub_route_id)

    async def test_topic_routing(self):
        # Create route with specific topic ID
        route_id = await RouteManager.create_route(
            user_id=123456789,
            name="Forum Route",
            source_chat_id=-100999888777,
            source_chat_title="Source Forum",
            source_chat_type="supergroup",
            source_topic_id=42,
            dest_chat_id=-100555666777,
            dest_chat_title="Dest Channel",
            dest_chat_type="channel"
        )

        # Query matching topic
        matching = await RouteManager.get_active_routes_for_source(-100999888777, source_topic_id=42)
        self.assertEqual(len(matching), 1)

        # Clean up
        await RouteManager.delete_route(route_id)

    def test_text_transformer(self):
        filters = {
            "allow_text": 1,
            "remove_links": 1,
            "remove_usernames": 1,
            "keyword_whitelist": "",
            "keyword_blacklist": "scam, fake"
        }
        customs = {
            "header_text": "🔥 BREAKING NEWS",
            "footer_text": "🔗 Follow @NewChannel"
        }
        replacements = [
            {"find_text": "Bitcoin", "replace_text": "BTC", "is_regex": 0},
            {"find_text": r"discount \d+%", "replace_text": "SPECIAL SALE", "is_regex": 1}
        ]

        original_text = "Check Bitcoin update! Contact @SupportAgent or visit https://scamsite.org with discount 50% now."

        result = MessageTransformer.transform_text(
            original_text,
            filters=filters,
            customizations=customs,
            replacements=replacements
        )

        self.assertTrue(result.startswith("🔥 BREAKING NEWS"))
        self.assertTrue(result.endswith("🔗 Follow @NewChannel"))
        self.assertIn("BTC", result)
        self.assertNotIn("Bitcoin", result)
        self.assertIn("SPECIAL SALE", result)
        self.assertNotIn("https://scamsite.org", result)
        self.assertNotIn("@SupportAgent", result)

    def test_filter_should_forward(self):
        photo_msg = DummyMessage(caption="Beautiful sunset", content_type="photo")
        should_fwd, reason = MessageTransformer.should_forward(photo_msg, {"allow_photo": 0})
        self.assertFalse(should_fwd)
        self.assertIn("photo media type disabled", reason)

        scam_msg = DummyMessage(text="Click for free crypto giveaway now!", content_type="text")
        should_fwd, reason = MessageTransformer.should_forward(scam_msg, {"keyword_blacklist": "scam, giveaway"})
        self.assertFalse(should_fwd)
        self.assertIn("matched blacklisted keyword", reason)

        valid_msg = DummyMessage(text="Important Bitcoin price analysis", content_type="text")
        should_fwd, _ = MessageTransformer.should_forward(valid_msg, {"keyword_whitelist": "bitcoin, ethereum"})
        self.assertTrue(should_fwd)

    def test_link_and_username_regex_patterns(self):
        import re

        invite_pattern = r'(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:me|dog))/(?:\+|joinchat/)([\w-]+)|^\+([\w-]+)$'
        username_pattern = r'(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:me|dog))/([a-zA-Z0-9_]{4,})|@([a-zA-Z0-9_]{4,})'

        # Test various invite link formats
        test_invites = [
            "https://t.me/+AbCdEf123",
            "http://t.me/+AbCdEf123",
            "t.me/+AbCdEf123",
            "https://telegram.me/+AbCdEf123",
            "https://t.me/joinchat/AbCdEf123",
            "+AbCdEf123"
        ]
        for inv in test_invites:
            m = re.search(invite_pattern, inv.strip())
            self.assertIsNotNone(m, f"Failed to match invite link: {inv}")
            invite_hash = m.group(1) or m.group(2)
            self.assertEqual(invite_hash, "AbCdEf123")

        # Test public usernames and channel links
        test_usernames = [
            "@crypto_signals",
            "https://t.me/crypto_signals",
            "http://telegram.me/crypto_signals",
            "t.me/crypto_signals"
        ]
        for usr in test_usernames:
            m = re.search(username_pattern, usr.strip())
            self.assertIsNotNone(m, f"Failed to match username: {usr}")
            target = m.group(1) or m.group(2)
            self.assertEqual(target, "crypto_signals")

    def test_router_structure(self):
        router = get_main_router()
        self.assertIsNotNone(router)
        self.assertTrue(len(router.sub_routers) >= 5)

    def test_main_menu_kb_admin_vs_normal_user(self):
        from bot.keyboards.inline import get_main_menu_kb

        admin_id = 123456789
        normal_user_id = 999999999

        # Admin keyboard
        admin_kb = get_main_menu_kb(admin_id)
        admin_btn_texts = [btn.text for row in admin_kb.inline_keyboard for btn in row]
        self.assertTrue(any("Host Userbot Setup" in t for t in admin_btn_texts))

        # Normal user keyboard
        normal_kb = get_main_menu_kb(normal_user_id)
        normal_btn_texts = [btn.text for row in normal_kb.inline_keyboard for btn in row]
        self.assertFalse(any("Host Userbot Setup" in t for t in normal_btn_texts))
        self.assertTrue(any("User Guide" in t for t in normal_btn_texts))

        # Anonymous / None user keyboard
        anon_kb = get_main_menu_kb(None)
        anon_btn_texts = [btn.text for row in anon_kb.inline_keyboard for btn in row]
        self.assertFalse(any("Host Userbot Setup" in t for t in anon_btn_texts))

    async def test_route_user_isolation(self):
        from bot.handlers.routes_manager import can_access_route

        user_a = 777111
        user_b = 888222
        admin_id = 123456789

        # User A creates a route
        route_a_id = await RouteManager.create_route(
            user_id=user_a,
            name="User A Private Route",
            source_chat_id=-100777111222,
            source_chat_title="User A Source",
            source_chat_type="channel",
            dest_chat_id=-100777333444,
            dest_chat_title="User A Dest",
            dest_chat_type="channel",
            forward_mode="copy"
        )
        route_a = await RouteManager.get_route(route_a_id)

        # 1. User A sees their own route
        routes_a = await RouteManager.get_routes_by_user(user_a)
        self.assertTrue(any(r["id"] == route_a_id for r in routes_a))

        # 2. User B has NO routes and CANNOT see User A's route
        routes_b = await RouteManager.get_routes_by_user(user_b)
        self.assertFalse(any(r["id"] == route_a_id for r in routes_b))
        self.assertEqual(len(routes_b), 0)

        # 3. Access permission checks
        self.assertTrue(can_access_route(route_a, user_a))
        self.assertFalse(can_access_route(route_a, user_b))
        self.assertTrue(can_access_route(route_a, admin_id))

    def test_empty_routes_kb(self):
        from bot.keyboards.inline import get_empty_routes_kb

        kb = get_empty_routes_kb()
        btn_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        btn_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]

        self.assertEqual(len(btn_texts), 2)
        self.assertIn("➕ Add New Route", btn_texts)
        self.assertIn("🏠 Back to Main Menu", btn_texts)
        self.assertIn("wizard:start", btn_callbacks)
        self.assertIn("menu:home", btn_callbacks)

    def test_help_and_stats_kb(self):
        from bot.keyboards.inline import get_help_kb, get_stats_kb, get_dev_info_kb

        # Help keyboard (now 3 buttons: Add Route, Developer Info, Main Menu)
        help_kb = get_help_kb()
        help_btn_texts = [btn.text for row in help_kb.inline_keyboard for btn in row]
        help_btn_callbacks = [btn.callback_data for row in help_kb.inline_keyboard for btn in row]
        self.assertEqual(len(help_btn_texts), 3)
        self.assertEqual(help_btn_texts[0], "➕ Add New Route")
        self.assertEqual(help_btn_texts[1], "👨‍💻 Developer Info")
        self.assertEqual(help_btn_texts[2], "🏠 Back to Main Menu")
        self.assertEqual(help_btn_callbacks[0], "wizard:start")
        self.assertEqual(help_btn_callbacks[1], "menu:dev_info")
        self.assertEqual(help_btn_callbacks[2], "menu:home")

        # Developer Info keyboard (Row 1: Make Your Own Bot URL, Row 2: Back to User Guide & Back to Main Menu)
        dev_kb = get_dev_info_kb()
        self.assertEqual(len(dev_kb.inline_keyboard), 2)
        # Row 1
        self.assertEqual(len(dev_kb.inline_keyboard[0]), 1)
        self.assertIn("Make Your Own Bot", dev_kb.inline_keyboard[0][0].text)
        self.assertEqual(dev_kb.inline_keyboard[0][0].url, "https://app.qufork.com/templates?template=tpl_1788018445033_telegram_forwarder_b")
        # Row 2 (2 buttons in same line)
        self.assertEqual(len(dev_kb.inline_keyboard[1]), 2)
        self.assertIn("Back to User Guide", dev_kb.inline_keyboard[1][0].text)
        self.assertEqual(dev_kb.inline_keyboard[1][0].callback_data, "menu:help")
        self.assertIn("Back to Main Menu", dev_kb.inline_keyboard[1][1].text)
        self.assertEqual(dev_kb.inline_keyboard[1][1].callback_data, "menu:home")

        # Stats keyboard
        stats_kb = get_stats_kb()
        stats_btn_texts = [btn.text for row in stats_kb.inline_keyboard for btn in row]
        stats_btn_callbacks = [btn.callback_data for row in stats_kb.inline_keyboard for btn in row]
        self.assertEqual(len(stats_btn_texts), 3)
        self.assertIn("➕ Add New Route", stats_btn_texts)
        self.assertIn("🔄 Refresh Stats", stats_btn_texts)
        self.assertIn("🏠 Back to Main Menu", stats_btn_texts)
        self.assertNotIn("Live Stats", stats_btn_texts)
        self.assertIn("wizard:start", stats_btn_callbacks)
        self.assertIn("menu:stats", stats_btn_callbacks)
        self.assertIn("menu:home", stats_btn_callbacks)

if __name__ == "__main__":
    unittest.main()





