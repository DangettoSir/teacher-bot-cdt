import json
from datetime import datetime, timezone

import aiosqlite
from cryptography.fernet import Fernet


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(
        self,
        path: str,
        encryption_key: str,
    ):
        self.path = path
        self.fernet = Fernet(
            encryption_key.encode()
        )

    def encrypt(self, value: str) -> bytes:
        return self.fernet.encrypt(
            value.encode()
        )

    def decrypt(self, value: bytes) -> str:
        return self.fernet.decrypt(value).decode()

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                PRAGMA journal_mode=WAL
                """
            )

            await db.execute(
                """
                PRAGMA synchronous=NORMAL
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS teachers (
                    telegram_id INTEGER PRIMARY KEY,

                    login TEXT NOT NULL,

                    encrypted_password BLOB NOT NULL,

                    encrypted_session BLOB,

                    schedule_hash TEXT,

                    schedule_json TEXT,

                    last_successful_check TEXT,

                    enabled INTEGER NOT NULL DEFAULT 1,

                    created_at TEXT NOT NULL,

                    updated_at TEXT NOT NULL
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    telegram_id INTEGER NOT NULL,

                    text TEXT NOT NULL,

                    created_at TEXT NOT NULL,

                    attempts INTEGER NOT NULL DEFAULT 0,

                    next_attempt_at TEXT NOT NULL,

                    sent_at TEXT,

                    FOREIGN KEY (
                        telegram_id
                    )
                    REFERENCES teachers (
                        telegram_id
                    )
                )
                """
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_notification_queue_pending
                ON notification_queue (
                    sent_at,
                    next_attempt_at
                )
                """
            )

            await db.commit()

    async def save_teacher(
        self,
        telegram_id: int,
        login: str,
        password: str,
        session_cookie: str,
    ):
        encrypted_password = self.encrypt(
            password
        )

        encrypted_session = self.encrypt(
            session_cookie
        )

        now = utc_now()

        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO teachers (
                    telegram_id,
                    login,
                    encrypted_password,
                    encrypted_session,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)

                ON CONFLICT(telegram_id)
                DO UPDATE SET
                    login = excluded.login,
                    encrypted_password =
                        excluded.encrypted_password,
                    encrypted_session =
                        excluded.encrypted_session,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    telegram_id,
                    login,
                    encrypted_password,
                    encrypted_session,
                    now,
                    now,
                ),
            )

            await db.commit()

    async def get_teacher(
        self,
        telegram_id: int,
    ):
        async with aiosqlite.connect(
            self.path
        ) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT *
                FROM teachers
                WHERE telegram_id = ?
                """,
                (telegram_id,),
            )

            return await cursor.fetchone()

    async def get_enabled_teachers(self):
        async with aiosqlite.connect(
            self.path
        ) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT *
                FROM teachers
                WHERE enabled = 1
                ORDER BY telegram_id
                """
            )

            return await cursor.fetchall()

    async def update_session(
        self,
        telegram_id: int,
        session_cookie: str,
    ):
        encrypted = self.encrypt(
            session_cookie
        )

        async with aiosqlite.connect(
            self.path
        ) as db:
            await db.execute(
                """
                UPDATE teachers
                SET
                    encrypted_session = ?,
                    updated_at = ?
                WHERE telegram_id = ?
                """,
                (
                    encrypted,
                    utc_now(),
                    telegram_id,
                ),
            )

            await db.commit()

    async def get_password(
        self,
        teacher,
    ) -> str:
        return self.decrypt(
            teacher["encrypted_password"]
        )

    async def get_session(
        self,
        teacher,
    ) -> str | None:
        value = teacher["encrypted_session"]

        if not value:
            return None

        return self.decrypt(value)

    async def commit_schedule_change(
        self,
        telegram_id: int,
        schedule_hash: str,
        schedule: list,
        notification_text: str | None,
    ):
        """
        Атомарно:

        1. сохраняем новое расписание;
        2. сохраняем notification_queue.

        Поэтому между этими двумя операциями не может
        возникнуть состояния "расписание уже новое,
        а уведомление потерялось".
        """

        now = utc_now()

        async with aiosqlite.connect(
            self.path
        ) as db:
            await db.execute("BEGIN IMMEDIATE")

            await db.execute(
                """
                UPDATE teachers
                SET
                    schedule_hash = ?,
                    schedule_json = ?,
                    last_successful_check = ?,
                    updated_at = ?
                WHERE telegram_id = ?
                """,
                (
                    schedule_hash,
                    json.dumps(
                        schedule,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    now,
                    now,
                    telegram_id,
                ),
            )

            if notification_text:
                await db.execute(
                    """
                    INSERT INTO notification_queue (
                        telegram_id,
                        text,
                        created_at,
                        next_attempt_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        telegram_id,
                        notification_text,
                        now,
                        now,
                    ),
                )

            await db.commit()

    async def mark_success_without_change(
        self,
        telegram_id: int,
    ):
        async with aiosqlite.connect(
            self.path
        ) as db:
            await db.execute(
                """
                UPDATE teachers
                SET
                    last_successful_check = ?,
                    updated_at = ?
                WHERE telegram_id = ?
                """,
                (
                    utc_now(),
                    utc_now(),
                    telegram_id,
                ),
            )

            await db.commit()

    async def get_pending_notifications(
        self,
        limit: int = 20,
    ):
        async with aiosqlite.connect(
            self.path
        ) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT *
                FROM notification_queue
                WHERE
                    sent_at IS NULL
                    AND next_attempt_at <= ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (
                    utc_now(),
                    limit,
                ),
            )

            return await cursor.fetchall()

    async def mark_notification_sent(
        self,
        notification_id: int,
    ):
        async with aiosqlite.connect(
            self.path
        ) as db:
            await db.execute(
                """
                UPDATE notification_queue
                SET sent_at = ?
                WHERE id = ?
                """,
                (
                    utc_now(),
                    notification_id,
                ),
            )

            await db.commit()

    async def mark_notification_failed(
        self,
        notification_id: int,
        attempts: int,
        retry_after: int,
    ):
        from datetime import timedelta

        next_attempt = (
            datetime.now(timezone.utc)
            + timedelta(seconds=retry_after)
        ).isoformat()

        async with aiosqlite.connect(
            self.path
        ) as db:
            await db.execute(
                """
                UPDATE notification_queue
                SET
                    attempts = ?,
                    next_attempt_at = ?
                WHERE id = ?
                """,
                (
                    attempts,
                    next_attempt,
                    notification_id,
                ),
            )

            await db.commit()

    async def cleanup_notifications(
        self,
        keep_days: int = 30,
    ):
        from datetime import timedelta

        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=keep_days)
        ).isoformat()

        async with aiosqlite.connect(
            self.path
        ) as db:
            await db.execute(
                """
                DELETE FROM notification_queue
                WHERE
                    sent_at IS NOT NULL
                    AND sent_at < ?
                """,
                (cutoff,),
            )

            await db.commit()