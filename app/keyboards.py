from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сегодня",
                    callback_data="schedule:today",
                ),
                InlineKeyboardButton(
                    text="Завтра",
                    callback_data="schedule:tomorrow",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Неделя",
                    callback_data="schedule:week",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Обновить",
                    callback_data="schedule:refresh",
                ),
            ],
        ]
    )