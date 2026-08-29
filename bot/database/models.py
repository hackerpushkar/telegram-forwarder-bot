from typing import Optional, List, Dict, Any
from .db import get_db

class RouteManager:
    @staticmethod
    async def create_route(
        user_id: int,
        name: str,
        source_chat_id: int,
        source_chat_title: str,
        source_chat_type: str,
        dest_chat_id: int,
        dest_chat_title: str,
        dest_chat_type: str,
        forward_mode: str = "copy",
        source_mode: str = "bot",
        source_topic_id: Optional[int] = None,
        dest_topic_id: Optional[int] = None,
    ) -> int:
        async with get_db() as db:
            cursor = await db.execute(
                """
                INSERT INTO routes (
                    user_id, name, source_chat_id, source_chat_title, source_chat_type,
                    source_topic_id, source_mode, dest_chat_id, dest_chat_title, dest_chat_type,
                    dest_topic_id, forward_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, name, source_chat_id, source_chat_title, source_chat_type,
                    source_topic_id, source_mode, dest_chat_id, dest_chat_title, dest_chat_type,
                    dest_topic_id, forward_mode
                )
            )
            route_id = cursor.lastrowid

            # Create default filters & customizations
            await db.execute(
                "INSERT INTO route_filters (route_id) VALUES (?)",
                (route_id,)
            )
            await db.execute(
                "INSERT INTO route_customizations (route_id) VALUES (?)",
                (route_id,)
            )
            await db.commit()
            return route_id

    @staticmethod
    async def get_route(route_id: int) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM routes WHERE id = ?", (route_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    async def get_routes_by_user(user_id: int) -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM routes WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_all_routes() -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM routes ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_active_routes_for_source(
        source_chat_id: int,
        source_topic_id: Optional[int] = None,
        source_mode: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async with get_db() as db:
            # Query variations to account for possible -100 prefix differences between MTProto and Bot API
            queries = [source_chat_id]
            if str(source_chat_id).startswith("-100"):
                queries.append(int(str(source_chat_id)[4:]))
            elif str(source_chat_id).isdigit():
                queries.append(int(f"-100{source_chat_id}"))

            placeholders = ",".join("?" for _ in queries)
            
            sql = f"SELECT * FROM routes WHERE source_chat_id IN ({placeholders}) AND is_active = 1"
            params = list(queries)

            if source_mode:
                sql += " AND source_mode = ?"
                params.append(source_mode)

            if source_topic_id is not None:
                sql += " AND (source_topic_id IS NULL OR source_topic_id = ?)"
                params.append(source_topic_id)

            cursor = await db.execute(sql, tuple(params))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def toggle_route_active(route_id: int) -> bool:
        async with get_db() as db:
            await db.execute(
                "UPDATE routes SET is_active = 1 - is_active WHERE id = ?",
                (route_id,)
            )
            await db.commit()
            route = await RouteManager.get_route(route_id)
            return bool(route["is_active"]) if route else False

    @staticmethod
    async def update_forward_mode(route_id: int, mode: str) -> None:
        async with get_db() as db:
            await db.execute(
                "UPDATE routes SET forward_mode = ? WHERE id = ?",
                (mode, route_id)
            )
            await db.commit()

    @staticmethod
    async def update_route_name(route_id: int, name: str) -> None:
        async with get_db() as db:
            await db.execute(
                "UPDATE routes SET name = ? WHERE id = ?",
                (name, route_id)
            )
            await db.commit()

    @staticmethod
    async def delete_route(route_id: int) -> None:
        async with get_db() as db:
            await db.execute("DELETE FROM routes WHERE id = ?", (route_id,))
            await db.commit()

    # --- Filters ---
    @staticmethod
    async def get_filters(route_id: int) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM route_filters WHERE route_id = ?", (route_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    async def toggle_filter_option(route_id: int, column: str) -> int:
        valid_cols = [
            "allow_text", "allow_photo", "allow_video", "allow_document",
            "allow_audio", "allow_voice", "allow_animation", "allow_sticker",
            "allow_poll", "remove_links", "remove_usernames"
        ]
        if column not in valid_cols:
            raise ValueError(f"Invalid column: {column}")

        async with get_db() as db:
            await db.execute(
                f"UPDATE route_filters SET {column} = 1 - {column} WHERE route_id = ?",
                (route_id,)
            )
            await db.commit()
            filters = await RouteManager.get_filters(route_id)
            return filters[column] if filters else 0

    @staticmethod
    async def update_keywords(route_id: int, whitelist: Optional[str] = None, blacklist: Optional[str] = None) -> None:
        async with get_db() as db:
            if whitelist is not None:
                await db.execute(
                    "UPDATE route_filters SET keyword_whitelist = ? WHERE route_id = ?",
                    (whitelist, route_id)
                )
            if blacklist is not None:
                await db.execute(
                    "UPDATE route_filters SET keyword_blacklist = ? WHERE route_id = ?",
                    (blacklist, route_id)
                )
            await db.commit()

    # --- Customizations ---
    @staticmethod
    async def get_customizations(route_id: int) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM route_customizations WHERE route_id = ?", (route_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    async def update_customizations(
        route_id: int,
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        pin_message: Optional[int] = None,
        protect_content: Optional[int] = None
    ) -> None:
        async with get_db() as db:
            updates = []
            params = []
            if header_text is not None:
                updates.append("header_text = ?")
                params.append(header_text)
            if footer_text is not None:
                updates.append("footer_text = ?")
                params.append(footer_text)
            if pin_message is not None:
                updates.append("pin_message = ?")
                params.append(pin_message)
            if protect_content is not None:
                updates.append("protect_content = ?")
                params.append(protect_content)

            if updates:
                params.append(route_id)
                await db.execute(
                    f"UPDATE route_customizations SET {', '.join(updates)} WHERE route_id = ?",
                    tuple(params)
                )
                await db.commit()

    # --- Replacements ---
    @staticmethod
    async def get_replacements(route_id: int) -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM route_replacements WHERE route_id = ?",
                (route_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def add_replacement(route_id: int, find_text: str, replace_text: str, is_regex: bool = False) -> int:
        async with get_db() as db:
            cursor = await db.execute(
                """
                INSERT INTO route_replacements (route_id, find_text, replace_text, is_regex)
                VALUES (?, ?, ?, ?)
                """,
                (route_id, find_text, replace_text, 1 if is_regex else 0)
            )
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def delete_replacement(replacement_id: int) -> None:
        async with get_db() as db:
            await db.execute(
                "DELETE FROM route_replacements WHERE id = ?",
                (replacement_id,)
            )
            await db.commit()

class UserbotAuthManager:
    @staticmethod
    async def save_session_string(session_string: str) -> None:
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO userbot_auth (id, session_string) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET session_string = ?
                """,
                (session_string, session_string)
            )
            await db.commit()

    @staticmethod
    async def get_session_string() -> Optional[str]:
        async with get_db() as db:
            cursor = await db.execute("SELECT session_string FROM userbot_auth WHERE id = 1")
            row = await cursor.fetchone()
            return row["session_string"] if row else None

    @staticmethod
    async def clear_session() -> None:
        async with get_db() as db:
            await db.execute("DELETE FROM userbot_auth WHERE id = 1")
            await db.commit()

class StatsManager:
    @staticmethod
    async def increment(key: str, by: int = 1) -> None:
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO bot_stats (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = value + ?
                """,
                (key, by, by)
            )
            await db.commit()

    @staticmethod
    async def get_all() -> Dict[str, int]:
        async with get_db() as db:
            cursor = await db.execute("SELECT key, value FROM bot_stats")
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}
