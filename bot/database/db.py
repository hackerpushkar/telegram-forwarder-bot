from contextlib import asynccontextmanager
import aiosqlite
import logging
from bot.config import config

logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        yield db

async def init_db():
    """Initialize database tables with migrations"""
    async with get_db() as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            source_chat_id INTEGER NOT NULL,
            source_chat_title TEXT,
            source_chat_type TEXT DEFAULT 'channel',
            source_topic_id INTEGER DEFAULT NULL,
            source_mode TEXT DEFAULT 'bot',
            dest_chat_id INTEGER NOT NULL,
            dest_chat_title TEXT,
            dest_chat_type TEXT DEFAULT 'channel',
            dest_topic_id INTEGER DEFAULT NULL,
            is_active INTEGER DEFAULT 1,
            forward_mode TEXT DEFAULT 'copy',
            forward_delay_sec INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Migration: Ensure source_mode column exists
        try:
            await db.execute("ALTER TABLE routes ADD COLUMN source_mode TEXT DEFAULT 'bot';")
        except Exception:
            pass  # Column already exists

        await db.execute("""
        CREATE TABLE IF NOT EXISTS route_filters (
            route_id INTEGER PRIMARY KEY,
            allow_text INTEGER DEFAULT 1,
            allow_photo INTEGER DEFAULT 1,
            allow_video INTEGER DEFAULT 1,
            allow_document INTEGER DEFAULT 1,
            allow_audio INTEGER DEFAULT 1,
            allow_voice INTEGER DEFAULT 1,
            allow_animation INTEGER DEFAULT 1,
            allow_sticker INTEGER DEFAULT 1,
            allow_poll INTEGER DEFAULT 1,
            keyword_whitelist TEXT DEFAULT '',
            keyword_blacklist TEXT DEFAULT '',
            remove_links INTEGER DEFAULT 0,
            remove_usernames INTEGER DEFAULT 0,
            FOREIGN KEY(route_id) REFERENCES routes(id) ON DELETE CASCADE
        );
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS route_customizations (
            route_id INTEGER PRIMARY KEY,
            header_text TEXT DEFAULT '',
            footer_text TEXT DEFAULT '',
            pin_message INTEGER DEFAULT 0,
            protect_content INTEGER DEFAULT 0,
            FOREIGN KEY(route_id) REFERENCES routes(id) ON DELETE CASCADE
        );
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS route_replacements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL,
            find_text TEXT NOT NULL,
            replace_text TEXT NOT NULL,
            is_regex INTEGER DEFAULT 0,
            FOREIGN KEY(route_id) REFERENCES routes(id) ON DELETE CASCADE
        );
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_stats (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        );
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS userbot_auth (
            id INTEGER PRIMARY KEY,
            phone TEXT,
            phone_code_hash TEXT,
            session_string TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_routes_source ON routes (source_chat_id, is_active);
        """)

        # Initialize stats default keys
        for key in ["total_forwarded", "total_errors", "total_filtered", "userbot_forwarded"]:
            await db.execute(
                "INSERT OR IGNORE INTO bot_stats (key, value) VALUES (?, 0)",
                (key,)
            )

        await db.commit()
        logger.info("Database initialized successfully at %s", config.DB_PATH)
