import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    webhook_base_url: str
    webhook_path: str
    webhook_secret: str
    encryption_key: str
    port: int
    poll_interval: int
    request_timeout: int
    notification_retry_interval: int


def load_config() -> Config:
    required = (
        "BOT_TOKEN",
        "WEBHOOK_BASE_URL",
        "WEBHOOK_PATH",
        "WEBHOOK_SECRET",
        "ENCRYPTION_KEY",
    )

    missing = [
        name
        for name in required
        if not os.getenv(name)
    ]

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )

    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        webhook_base_url=os.environ["WEBHOOK_BASE_URL"].rstrip("/"),
        webhook_path=os.environ["WEBHOOK_PATH"],
        webhook_secret=os.environ["WEBHOOK_SECRET"],
        encryption_key=os.environ["ENCRYPTION_KEY"],
        port=int(os.getenv("PORT", "8080")),
        poll_interval=int(
            os.getenv("POLL_INTERVAL", "600")
        ),
        request_timeout=int(
            os.getenv("REQUEST_TIMEOUT", "20")
        ),
        notification_retry_interval=int(
            os.getenv(
                "NOTIFICATION_RETRY_INTERVAL",
                "30",
            )
        ),
    )