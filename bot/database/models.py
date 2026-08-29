import datetime
from typing import Optional, List, Dict, Any
from .db import get_db, is_mongo_enabled, get_mongo_db, get_next_sequence

def _clean_mongo_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    d = dict(doc)
    d.pop("_id", None)
    return d

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
        if is_mongo_enabled():
            db = get_mongo_db()
            route_id = await get_next_sequence("route_id")
            route_doc = {
                "id": route_id,
                "user_id": user_id,
                "name": name,
                "source_chat_id": source_chat_id,
                "source_chat_title": source_chat_title,
                "source_chat_type": source_chat_type,
                "source_topic_id": source_topic_id,
                "source_mode": source_mode,
                "dest_chat_id": dest_chat_id,
                "dest_chat_title": dest_chat_title,
                "dest_chat_type": dest_chat_type,
                "dest_topic_id": dest_topic_id,
                "is_active": 1,
                "forward_mode": forward_mode,
                "forward_delay_sec": 0,
                "created_at": datetime.datetime.utcnow().isoformat()
            }
            await db.routes.insert_one(route_doc)

            # Default filters
            await db.route_filters.insert_one({
                "route_id": route_id,
                "allow_text": 1,
                "allow_photo": 1,
                "allow_video": 1,
                "allow_document": 1,
                "allow_audio": 1,
                "allow_voice": 1,
                "allow_animation": 1,
                "allow_sticker": 1,
                "allow_poll": 1,
                "keyword_whitelist": "",
                "keyword_blacklist": "",
                "remove_links": 0,
                "remove_usernames": 0
            })

            # Default customizations
            await db.route_customizations.insert_one({
                "route_id": route_id,
                "header_text": "",
                "footer_text": "",
                "pin_message": 0,
                "protect_content": 0
            })

            return route_id

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
        if is_mongo_enabled():
            db = get_mongo_db()
            doc = await db.routes.find_one({"id": route_id})
            return _clean_mongo_doc(doc)

        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM routes WHERE id = ?", (route_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    async def get_routes_by_user(user_id: int) -> List[Dict[str, Any]]:
        if is_mongo_enabled():
            db = get_mongo_db()
            cursor = db.routes.find({"user_id": user_id}).sort("id", -1)
            docs = await cursor.to_list(length=1000)
            return [_clean_mongo_doc(d) for d in docs]

        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM routes WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_all_routes() -> List[Dict[str, Any]]:
        if is_mongo_enabled():
            db = get_mongo_db()
            cursor = db.routes.find({}).sort("id", -1)
            docs = await cursor.to_list(length=1000)
            return [_clean_mongo_doc(d) for d in docs]

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
        # Account for possible -100 prefix differences between MTProto and Bot API
        queries = [source_chat_id]
        if str(source_chat_id).startswith("-100"):
            queries.append(int(str(source_chat_id)[4:]))
        elif str(source_chat_id).isdigit():
            queries.append(int(f"-100{source_chat_id}"))

        if is_mongo_enabled():
            db = get_mongo_db()
            query: Dict[str, Any] = {
                "source_chat_id": {"$in": queries},
                "is_active": 1
            }
            if source_mode:
                query["source_mode"] = source_mode
            if source_topic_id is not None:
                query["$or"] = [
                    {"source_topic_id": None},
                    {"source_topic_id": source_topic_id}
                ]
            cursor = db.routes.find(query)
            docs = await cursor.to_list(length=500)
            return [_clean_mongo_doc(d) for d in docs]

        async with get_db() as db:
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
        if is_mongo_enabled():
            db = get_mongo_db()
            route = await db.routes.find_one({"id": route_id})
            if not route:
                return False
            new_active = 0 if route.get("is_active", 1) == 1 else 1
            await db.routes.update_one({"id": route_id}, {"$set": {"is_active": new_active}})
            return bool(new_active)

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
        if is_mongo_enabled():
            db = get_mongo_db()
            await db.routes.update_one({"id": route_id}, {"$set": {"forward_mode": mode}})
            return

        async with get_db() as db:
            await db.execute(
                "UPDATE routes SET forward_mode = ? WHERE id = ?",
                (mode, route_id)
            )
            await db.commit()

    @staticmethod
    async def update_route_name(route_id: int, name: str) -> None:
        if is_mongo_enabled():
            db = get_mongo_db()
            await db.routes.update_one({"id": route_id}, {"$set": {"name": name}})
            return

        async with get_db() as db:
            await db.execute(
                "UPDATE routes SET name = ? WHERE id = ?",
                (name, route_id)
            )
            await db.commit()

    @staticmethod
    async def delete_route(route_id: int) -> None:
        if is_mongo_enabled():
            db = get_mongo_db()
            await db.routes.delete_one({"id": route_id})
            await db.route_filters.delete_one({"route_id": route_id})
            await db.route_customizations.delete_one({"route_id": route_id})
            await db.route_replacements.delete_many({"route_id": route_id})
            return

        async with get_db() as db:
            await db.execute("DELETE FROM routes WHERE id = ?", (route_id,))
            await db.commit()

    # --- Filters ---
    @staticmethod
    async def get_filters(route_id: int) -> Optional[Dict[str, Any]]:
        if is_mongo_enabled():
            db = get_mongo_db()
            doc = await db.route_filters.find_one({"route_id": route_id})
            return _clean_mongo_doc(doc)

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

        if is_mongo_enabled():
            db = get_mongo_db()
            filters = await db.route_filters.find_one({"route_id": route_id})
            current_val = filters.get(column, 1) if filters else 1
            new_val = 0 if current_val == 1 else 1
            await db.route_filters.update_one(
                {"route_id": route_id},
                {"$set": {column: new_val}},
                upsert=True
            )
            return new_val

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
        if is_mongo_enabled():
            db = get_mongo_db()
            updates = {}
            if whitelist is not None:
                updates["keyword_whitelist"] = whitelist
            if blacklist is not None:
                updates["keyword_blacklist"] = blacklist
            if updates:
                await db.route_filters.update_one(
                    {"route_id": route_id},
                    {"$set": updates},
                    upsert=True
                )
            return

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
        if is_mongo_enabled():
            db = get_mongo_db()
            doc = await db.route_customizations.find_one({"route_id": route_id})
            return _clean_mongo_doc(doc)

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
        if is_mongo_enabled():
            db = get_mongo_db()
            updates = {}
            if header_text is not None:
                updates["header_text"] = header_text
            if footer_text is not None:
                updates["footer_text"] = footer_text
            if pin_message is not None:
                updates["pin_message"] = pin_message
            if protect_content is not None:
                updates["protect_content"] = protect_content
            if updates:
                await db.route_customizations.update_one(
                    {"route_id": route_id},
                    {"$set": updates},
                    upsert=True
                )
            return

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
        if is_mongo_enabled():
            db = get_mongo_db()
            cursor = db.route_replacements.find({"route_id": route_id}).sort("id", 1)
            docs = await cursor.to_list(length=500)
            return [_clean_mongo_doc(d) for d in docs]

        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM route_replacements WHERE route_id = ?",
                (route_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def add_replacement(route_id: int, find_text: str, replace_text: str, is_regex: bool = False) -> int:
        if is_mongo_enabled():
            db = get_mongo_db()
            repl_id = await get_next_sequence("replacement_id")
            doc = {
                "id": repl_id,
                "route_id": route_id,
                "find_text": find_text,
                "replace_text": replace_text,
                "is_regex": 1 if is_regex else 0
            }
            await db.route_replacements.insert_one(doc)
            return repl_id

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
        if is_mongo_enabled():
            db = get_mongo_db()
            await db.route_replacements.delete_one({"id": replacement_id})
            return

        async with get_db() as db:
            await db.execute(
                "DELETE FROM route_replacements WHERE id = ?",
                (replacement_id,)
            )
            await db.commit()

class UserbotAuthManager:
    @staticmethod
    async def save_session_string(session_string: str) -> None:
        if is_mongo_enabled():
            db = get_mongo_db()
            await db.userbot_auth.update_one(
                {"id": 1},
                {"$set": {
                    "id": 1,
                    "session_string": session_string,
                    "updated_at": datetime.datetime.utcnow().isoformat()
                }},
                upsert=True
            )
            return

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
        if is_mongo_enabled():
            db = get_mongo_db()
            doc = await db.userbot_auth.find_one({"id": 1})
            return doc.get("session_string") if doc else None

        async with get_db() as db:
            cursor = await db.execute("SELECT session_string FROM userbot_auth WHERE id = 1")
            row = await cursor.fetchone()
            return row["session_string"] if row else None

    @staticmethod
    async def clear_session() -> None:
        if is_mongo_enabled():
            db = get_mongo_db()
            await db.userbot_auth.delete_one({"id": 1})
            return

        async with get_db() as db:
            await db.execute("DELETE FROM userbot_auth WHERE id = 1")
            await db.commit()

class StatsManager:
    @staticmethod
    async def increment(key: str, by: int = 1) -> None:
        if is_mongo_enabled():
            db = get_mongo_db()
            await db.bot_stats.update_one(
                {"key": key},
                {"$inc": {"value": by}},
                upsert=True
            )
            return

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
        if is_mongo_enabled():
            db = get_mongo_db()
            cursor = db.bot_stats.find({})
            docs = await cursor.to_list(length=100)
            return {d["key"]: d.get("value", 0) for d in docs}

        async with get_db() as db:
            cursor = await db.execute("SELECT key, value FROM bot_stats")
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}
