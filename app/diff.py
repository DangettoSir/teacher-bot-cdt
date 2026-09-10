from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ScheduleChange:
    kind: str
    old: dict | None
    new: dict | None


def lesson_key(item: dict) -> tuple:
    """
    Уникальность занятия.

    ClID — конкретное занятие.
    SClID — конкретная подгруппа.
    """

    return (
        item.get("ClID", ""),
        item.get("SClID", ""),
    )


def lesson_signature(item: dict) -> tuple:
    """
    Все поля, изменение которых считаем
    изменением занятия.
    """

    subgroups = tuple(
        sorted(
            (
                (
                    subgroup.get("SClID"),
                    subgroup.get("SGrID"),
                    subgroup.get("SGCaID"),
                    subgroup.get("STopic"),
                    subgroup.get("STitle"),
                )
                for subgroup in item.get(
                    "SubGroup",
                    [],
                )
            )
        )
    )

    return (
        item.get("Day"),
        item.get("PrID"),
        item.get("ParaN"),
        item.get("group"),
        item.get("topic"),
        item.get("start"),
        item.get("end"),
        item.get("room"),
        item.get("color"),
        item.get("title"),
        subgroups,
    )


def diff_schedule(
    old_schedule: list[dict],
    new_schedule: list[dict],
) -> list[ScheduleChange]:

    old_map = {
        lesson_key(item): item
        for item in old_schedule
    }

    new_map = {
        lesson_key(item): item
        for item in new_schedule
    }

    changes: list[ScheduleChange] = []

    # Добавленные
    for key in sorted(
        new_map.keys() - old_map.keys()
    ):
        changes.append(
            ScheduleChange(
                kind="added",
                old=None,
                new=new_map[key],
            )
        )

    # Удалённые
    for key in sorted(
        old_map.keys() - new_map.keys()
    ):
        changes.append(
            ScheduleChange(
                kind="removed",
                old=old_map[key],
                new=None,
            )
        )

    # Изменённые
    for key in sorted(
        old_map.keys() & new_map.keys()
    ):
        old = old_map[key]
        new = new_map[key]

        if lesson_signature(old) != lesson_signature(new):
            changes.append(
                ScheduleChange(
                    kind="changed",
                    old=old,
                    new=new,
                )
            )

    return changes


def format_date(value: str) -> str:
    try:
        return datetime.fromisoformat(
            value
        ).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return value or "—"


def time_part(value: str) -> str:
    if not value:
        return "—"

    return value[-5:]


def lesson_text(item: dict) -> str:
    group = (
        item.get("group")
        or "Без группы"
    )

    title = (
        item.get("title")
        or item.get("topic")
        or "Без названия"
    )

    start = time_part(
        item.get("start", "")
    )

    end = time_part(
        item.get("end", "")
    )

    room = item.get("room")

    text = (
        f"<b>{format_date(item.get('Day'))}</b>\n"
        f"{item.get('ParaN', '?')} пара · "
        f"{start}–{end}\n"
        f"{group} · {title}"
    )

    if room:
        text += (
            f"\nАудитория: {room}"
        )

    return text


def format_changes(
    changes: list[ScheduleChange],
    recovery: bool = False,
) -> str:

    if not changes:
        return ""

    if recovery:
        text = (
            "⚠️ <b>Расписание изменилось</b>\n"
            "<i>"
            "Бот восстановился после недоступности "
            "и получил актуальное расписание."
            "</i>\n\n"
        )
    else:
        text = (
            "⚠️ <b>Расписание изменилось</b>\n\n"
        )

    for change in changes:

        if change.kind == "added":
            text += (
                "➕ <b>Добавлено</b>\n"
                f"{lesson_text(change.new)}\n\n"
            )

        elif change.kind == "removed":
            text += (
                "➖ <b>Удалено</b>\n"
                f"{lesson_text(change.old)}\n\n"
            )

        elif change.kind == "changed":
            text += (
                "✏️ <b>Изменено</b>\n\n"
                "<b>Было:</b>\n"
                f"{lesson_text(change.old)}\n\n"
                "<b>Стало:</b>\n"
                f"{lesson_text(change.new)}\n\n"
            )

    return text.strip()