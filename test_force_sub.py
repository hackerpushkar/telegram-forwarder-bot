import unittest
from unittest.mock import AsyncMock, MagicMock
import asyncio
from aiogram.enums import ChatMemberStatus
from bot.config import BotConfig
from bot.services.force_sub import parse_channel_info, check_force_sub
from bot.keyboards.inline import get_force_sub_kb

class TestForceSub(unittest.TestCase):
    def test_config_parsing_comma_separated(self):
        cfg = BotConfig(
            BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            FORCE_SUB_CHANNELS="@chan1, @chan2, https://t.me/chan3"
        )
        channels = cfg.get_configured_force_channels()
        self.assertEqual(len(channels), 3)
        self.assertEqual(channels[0], "@chan1")
        self.assertEqual(channels[1], "@chan2")
        self.assertEqual(channels[2], "https://t.me/chan3")

    def test_config_parsing_individual_keys_and_limit_12(self):
        data = {
            "BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "FORCE_SUB_CHANNELS": "@chan1,@chan2",
        }
        for i in range(1, 15):
            data[f"FORCE_SUB_{i}"] = f"@extra_chan_{i}"
        
        cfg = BotConfig(**data)
        channels = cfg.get_configured_force_channels()
        # Must be capped at 12 maximum
        self.assertEqual(len(channels), 12)
        self.assertIn("@chan1", channels)
        self.assertIn("@chan2", channels)

    def test_parse_channel_info_formats(self):
        # 1. @username
        res1 = parse_channel_info("@telegram", 1)
        self.assertEqual(res1["chat_id"], "@telegram")
        self.assertEqual(res1["url"], "https://t.me/telegram")
        self.assertEqual(res1["title"], "📢 @telegram")

        # 2. plain username
        res2 = parse_channel_info("mychannel", 2)
        self.assertEqual(res2["chat_id"], "@mychannel")
        self.assertEqual(res2["url"], "https://t.me/mychannel")

        # 3. https url
        res3 = parse_channel_info("https://t.me/superbot", 3)
        self.assertEqual(res3["chat_id"], "@superbot")
        self.assertEqual(res3["url"], "https://t.me/superbot")

        # 4. chat_id:invite_link
        res4 = parse_channel_info("-1001234567890:https://t.me/+abcdef123", 4)
        self.assertEqual(res4["chat_id"], -1001234567890)
        self.assertEqual(res4["url"], "https://t.me/+abcdef123")

    def test_get_force_sub_kb(self):
        unjoined = [
            {"title": "📢 @chan1", "url": "https://t.me/chan1", "chat_id": "@chan1"},
            {"title": "📢 @chan2", "url": "https://t.me/chan2", "chat_id": "@chan2"}
        ]
        kb = get_force_sub_kb(unjoined)
        self.assertEqual(len(kb.inline_keyboard), 3) # 2 channels + 1 verify button
        self.assertEqual(kb.inline_keyboard[0][0].url, "https://t.me/chan1")
        self.assertEqual(kb.inline_keyboard[1][0].url, "https://t.me/chan2")
        self.assertEqual(kb.inline_keyboard[2][0].callback_data, "fsub:verify")

    def test_check_force_sub_memberships(self):
        async def run_async_test():
            mock_bot = MagicMock()
            
            # Setup config with 2 channels
            from bot.config import config
            config.FORCE_SUB_CHANNELS = ["@chan1", "@chan2"]
            for i in range(1, 13):
                setattr(config, f"FORCE_SUB_{i}", None)


            # Case A: User is member in both
            member_obj = MagicMock()
            member_obj.status = ChatMemberStatus.MEMBER
            mock_bot.get_chat_member = AsyncMock(return_value=member_obj)

            is_sub, unjoined = await check_force_sub(mock_bot, 12345)
            self.assertTrue(is_sub)
            self.assertEqual(len(unjoined), 0)

            # Case B: User left channel 2
            def side_effect(chat_id, user_id):
                m = MagicMock()
                if chat_id == "@chan1":
                    m.status = ChatMemberStatus.MEMBER
                else:
                    m.status = ChatMemberStatus.LEFT
                return m

            mock_bot.get_chat_member = AsyncMock(side_effect=side_effect)
            is_sub, unjoined = await check_force_sub(mock_bot, 12345)
            self.assertFalse(is_sub)
            self.assertEqual(len(unjoined), 1)
            self.assertEqual(unjoined[0]["chat_id"], "@chan2")

            # Clean up config
            config.FORCE_SUB_CHANNELS = []

        asyncio.run(run_async_test())

if __name__ == "__main__":
    unittest.main()
