import asyncio

from .portal import TeacherPortal


async def check_portal() -> bool:
    portal = TeacherPortal(
        login="preflight",
        timeout=10,
    )

    try:
        return await portal.check_availability()

    finally:
        await portal.close()


async def main() -> int:
    available = await check_portal()

    if available:
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(
        asyncio.run(main())
    )