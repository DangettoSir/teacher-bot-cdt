import asyncio
import hashlib
import json
from datetime import date, timedelta

from aiogram import Bot

from .database import Database
from .diff import (
    diff_schedule,
    format_changes,
)
from .portal import (
    AuthenticationError,
    PortalUnavailableError,
    SessionExpiredError,
    TeacherPortal,
)


def normalize_schedule(
    schedule: list[dict],
) -> list[dict]:
    return sorted(
        schedule,
        key=lambda item: (
            item.get("Day", ""),
            str(item.get("ParaN", "")),
            item.get("ClID", ""),
            item.get("SClID", ""),
        ),
    )


def make_hash(
    schedule: list[dict],
) -> str:
    normalized = normalize_schedule(
        schedule
    )

    data = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        data.encode()
    ).hexdigest()


def format_schedule(
    schedule: list[dict],
) -> str:
    if not schedule:
        return (
            "<b>Расписание</b>\n\n"
            "Пар нет."
        )

    schedule = normalize_schedule(
        schedule
    )

    text = []
    current_day = None

    for item in schedule:
        day = item.get("Day")

        if day != current_day:
            current_day = day

            if text:
                text.append("")

            from .diff import format_date

            text.append(
                f"<b>{format_date(day)}</b>"
            )

        start = (
            item.get("start", "")[-5:]
        )

        end = (
            item.get("end", "")[-5:]
        )

        group = (
            item.get("group")
            or "Без группы"
        )

        title = (
            item.get("title")
            or item.get("topic")
            or "Без названия"
        )

        line = (
            f"<b>{item.get('ParaN', '?')} "
            f"пара</b> · "
            f"{start}–{end}\n"
            f"{group} · {title}"
        )

        room = item.get("room")

        if room:
            line += (
                f"\nАудитория: {room}"
            )

        text.append(line)

    return "\n\n".join(text)


async def get_schedule_with_reauth(
    db: Database,
    teacher,
    start: date,
    end: date,
):
    """
    Сначала используем только session cookie.

    Пароль расшифровывается ТОЛЬКО если session
    протухла.
    """

    session_cookie = await db.get_session(
        teacher
    )

    portal = TeacherPortal(
        login=teacher["login"],
        session_cookie=session_cookie,
    )

    try:
        try:
            schedule = await portal.get_schedule(
                teacher_uid=teacher["login"],
                start=start.isoformat(),
                end=end.isoformat(),
            )

            new_session = (
                portal.session_cookie
            )

            return schedule, new_session

        except SessionExpiredError:
            pass

    finally:
        await portal.close()

    password = await db.get_password(
        teacher
    )

    portal = TeacherPortal(
        login=teacher["login"],
        password=password,
    )

    try:
        new_session = (
            await portal.login_portal()
        )

        schedule = await portal.get_schedule(
            teacher_uid=teacher["login"],
            start=start.isoformat(),
            end=end.isoformat(),
        )

        return schedule, new_session

    finally:
        await portal.close()


async def check_teacher(
    bot: Bot,
    db: Database,
    teacher,
    recovery: bool = False,
):
    try:
        today = date.today()

        current, new_session = (
            await get_schedule_with_reauth(
                db=db,
                teacher=teacher,
                start=today,
                end=today + timedelta(days=7),
            )
        )

        if (
            new_session
            and new_session
            != await db.get_session(teacher)
        ):
            await db.update_session(
                teacher["telegram_id"],
                new_session,
            )

        current = normalize_schedule(
            current
        )

        current_hash = make_hash(
            current
        )

        old_hash = teacher[
            "schedule_hash"
        ]

        # Первое состояние.
        if not old_hash:
            await db.commit_schedule_change(
                telegram_id=teacher[
                    "telegram_id"
                ],
                schedule_hash=current_hash,
                schedule=current,
                notification_text=None,
            )

            return True

        # Ничего не поменялось.
        if old_hash == current_hash:
            await db.mark_success_without_change(
                teacher["telegram_id"]
            )

            return True

        old_schedule = []

        if teacher["schedule_json"]:
            old_schedule = json.loads(
                teacher["schedule_json"]
            )

        changes = diff_schedule(
            old_schedule,
            current,
        )

        if not changes:
            await db.commit_schedule_change(
                telegram_id=teacher[
                    "telegram_id"
                ],
                schedule_hash=current_hash,
                schedule=current,
                notification_text=None,
            )

            return True

        notification = format_changes(
            changes,
            recovery=recovery,
        )

        await db.commit_schedule_change(
            telegram_id=teacher[
                "telegram_id"
            ],
            schedule_hash=current_hash,
            schedule=current,
            notification_text=notification,
        )

        return True

    except (
        PortalUnavailableError,
        TimeoutError,
        ConnectionError,
    ):
        return False

    except AuthenticationError:
        return False

    except Exception:
        return False


async def run_check_cycle(
    bot: Bot,
    db: Database,
    recovery: bool = False,
) -> bool:
    teachers = (
        await db.get_enabled_teachers()
    )

    portal_available = True

    for teacher in teachers:
        result = await check_teacher(
            bot=bot,
            db=db,
            teacher=teacher,
            recovery=recovery,
        )

        if not result:
            portal_available = False

    return portal_available


async def notification_worker(
    bot: Bot,
    db: Database,
    retry_interval: int,
):
    while True:
        notifications = (
            await db.get_pending_notifications(
                limit=20
            )
        )

        for notification in notifications:
            try:
                await bot.send_message(
                    notification[
                        "telegram_id"
                    ],
                    notification["text"],
                )

                await db.mark_notification_sent(
                    notification["id"]
                )

            except Exception:
                attempts = (
                    notification["attempts"]
                    + 1
                )

                retry_after = min(
                    retry_interval
                    * (
                        2 ** min(
                            attempts,
                            7,
                        )
                    ),
                    3600,
                )

                await db.mark_notification_failed(
                    notification["id"],
                    attempts,
                    retry_after,
                )

        await asyncio.sleep(
            retry_interval
        )


async def scheduler_loop(
    bot: Bot,
    db: Database,
    interval: int,
):
    # ==================================================
    # STARTUP RECOVERY
    # ==================================================

    # Сразу после запуска проверяем всех.
    await run_check_cycle(
        bot,
        db,
        recovery=True,
    )

    # ==================================================
    # NORMAL LOOP
    # ==================================================

    while True:
        await asyncio.sleep(interval)

        await run_check_cycle(
            bot,
            db,
            recovery=False,
        )