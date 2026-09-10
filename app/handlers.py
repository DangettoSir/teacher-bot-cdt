from datetime import date, timedelta
import json
import hashlib

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    Message,
)

from .database import Database
from .diff import format_changes
from .keyboards import main_keyboard
from .portal import (
    AuthenticationError,
    TeacherPortal,
    PortalUnavailableError
)


router = Router()


class AuthState(StatesGroup):
    waiting_login = State()
    waiting_password = State()


def schedule_hash(
    schedule: list[dict],
) -> str:
    data = json.dumps(
        schedule,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        data.encode()
    ).hexdigest()


async def create_portal(
    db: Database,
    teacher,
) -> TeacherPortal:
    session_cookie = await db.get_session(
        teacher
    )

    return TeacherPortal(
        login=teacher["login"],
        session_cookie=session_cookie,
    )


@router.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext,
    db: Database,
):
    teacher = await db.get_teacher(
        message.from_user.id
    )

    if teacher:
        await state.clear()

        await message.answer(
            "Расписание преподавателя:",
            reply_markup=main_keyboard(),
        )

        return

    await state.set_state(
        AuthState.waiting_login
    )

    await message.answer(
        "Введите логин преподавателя (UID):"
    )


@router.message(AuthState.waiting_login)
async def login_received(
    message: Message,
    state: FSMContext,
):
    login = (
        message.text or ""
    ).strip()

    if not login:
        await message.answer(
            "Введите логин ещё раз."
        )
        return

    await state.update_data(
        login=login
    )

    await state.set_state(
        AuthState.waiting_password
    )

    await message.answer(
        "Введите пароль:"
    )


@router.message(AuthState.waiting_password)
async def password_received(
    message: Message,
    state: FSMContext,
    db: Database,
):
    password = message.text or ""

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()

    login = data.get("login")

    if not login:
        await state.clear()

        await message.answer(
            "Регистрация сброшена. "
            "Нажмите /start."
        )

        return

    portal = TeacherPortal(
        login=login,
        password=password,
    )

    try:
        session_cookie = (
            await portal.login_portal()
        )

        schedule = await portal.get_schedule(
            teacher_uid=login,
            start=date.today().isoformat(),
            end=(
                date.today()
                + timedelta(days=7)
            ).isoformat(),
        )

        await db.save_teacher(
            telegram_id=message.from_user.id,
            login=login,
            password=password,
            session_cookie=session_cookie,
        )

        await db.commit_schedule_change(
            telegram_id=message.from_user.id,
            schedule_hash=schedule_hash(
                schedule
            ),
            schedule=schedule,
            notification_text=None,
        )

        await state.clear()

        await message.answer(
            "Готово.\n\n"
            "Расписание подключено. "
            "Бот будет автоматически "
            "отслеживать изменения.",
            reply_markup=main_keyboard(),
        )

    except AuthenticationError:
        await message.answer(
            "Неверный логин или пароль.\n"
            "Попробуйте снова через /start."
        )

    except Exception as e:
        print(f"PORTAL ERROR: {type(e).__name__}: {e}", flush=True)

        await message.answer(
            "Не удалось подключиться "
            "к порталу. Попробуйте позже."
        )

    finally:
        await portal.close()


@router.callback_query(
    F.data.startswith("schedule:")
)
async def schedule_callback(
    callback: CallbackQuery,
    db: Database,
):
    await callback.answer(
        "Обновляю..."
    )

    teacher = await db.get_teacher(
        callback.from_user.id
    )

    if not teacher:
        await callback.message.answer(
            "Сначала выполните /start."
        )
        return

    action = callback.data.split(
        ":",
        1,
    )[1]

    today = date.today()

    if action == "today":
        start = today
        end = today

    elif action == "tomorrow":
        start = today + timedelta(days=1)
        end = start

    else:
        start = today
        end = today + timedelta(days=7)

    from .scheduler import (
        get_schedule_with_reauth,
        format_schedule,
    )

    try:
        schedule, new_session = (
            await get_schedule_with_reauth(
                db=db,
                teacher=teacher,
                start=start,
                end=end,
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

        text = format_schedule(
            schedule
        )

        await callback.message.edit_text(
            text,
            reply_markup=main_keyboard(),
        )

    except (
        PortalUnavailableError,
        TimeoutError,
        ConnectionError,
    ):
        await callback.message.edit_text(
            "Тех.работы на стороне Колледжа.\n\n"
            "Попробуйте обновить позже.",
            reply_markup=main_keyboard(),
        )

    except AuthenticationError:
        await callback.message.edit_text(
            "Не удалось авторизоваться "
            "на стороне Колледжа.\n\n"
            "Проверьте логин и пароль "
            "через /start.",
            reply_markup=main_keyboard(),
        )

    except Exception:
        await callback.message.edit_text(
            "Не удалось получить расписание.",
            reply_markup=main_keyboard(),
        )