import asyncio
import logging

from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import (
    DefaultBotProperties,
)
from aiogram.enums import ParseMode
from aiogram.types import Update

from app.config import load_config
from app.database import Database
from app.handlers import router
from app.portal import TeacherPortal
from app.scheduler import (
    notification_worker,
    scheduler_loop,
)


logging.basicConfig(
    level=logging.WARNING,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s: "
        "%(message)s"
    ),
)

logger = logging.getLogger(
    "teacher-bot"
)


async def preflight_portal() -> bool:
    portal = TeacherPortal(
        login="preflight",
        timeout=10,
    )

    try:
        return await portal.check_availability()

    finally:
        await portal.close()


async def main():
    config = load_config()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    db = Database(
        path="data/bot.db",
        encryption_key=config.encryption_key,
    )

    await db.init()

    # Проверяем колледж ДО запуска scheduler.

    portal_available = (
        await preflight_portal()
    )

    if not portal_available:
        logger.warning(
            "College portal is unavailable "
            "during startup"
        )

    dp = Dispatcher()

    dp["db"] = db

    dp.include_router(router)

    webhook_url = (
        config.webhook_base_url
        + config.webhook_path
    )

    await bot.set_webhook(
        url=webhook_url,
        secret_token=config.webhook_secret,
        allowed_updates=[
            "message",
            "callback_query",
        ],
        max_connections=10,
        drop_pending_updates=False,
    )

    app = web.Application()

    async def webhook(
        request: web.Request,
    ):
        secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token"
        )

        if secret != config.webhook_secret:
            return web.Response(
                status=403
            )

        try:
            data = await request.json()

            update = Update.model_validate(
                data,
                context={
                    "bot": bot
                },
            )

            await dp.feed_update(
                bot,
                update,
            )

            return web.Response(
                text="OK"
            )

        except Exception:
            logger.exception(
                "Webhook processing failed"
            )

            return web.Response(
                status=500
            )

    app.router.add_post(
        config.webhook_path,
        webhook,
    )

    scheduler_task = asyncio.create_task(
        scheduler_loop(
            bot,
            db,
            config.poll_interval,
        )
    )

    notification_task = asyncio.create_task(
        notification_worker(
            bot,
            db,
            config.notification_retry_interval,
        )
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=config.port,
    )

    await site.start()

    try:
        await asyncio.Event().wait()

    finally:
        scheduler_task.cancel()
        notification_task.cancel()

        await asyncio.gather(
            scheduler_task,
            notification_task,
            return_exceptions=True,
        )

        await bot.delete_webhook()

        await runner.cleanup()

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())