import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from bot.meta_api import DeliveryError, send_payload
from engine.timing import IST
from engine.weather import get_forecast
from storage import connect

logger = logging.getLogger(__name__)


def validate_alert_config(config: dict) -> None:
    if not all(
        config.get(k)
        for k in (
            "META_ALERT_TEMPLATE",
            "META_ACCESS_TOKEN",
            "META_PHONE_NUMBER_ID",
            "WEATHER_ENABLED",
        )
    ):
        raise ValueError(
            "Alerts require live weather, Meta credentials and an approved Hindi template."
        )


def dispatch_alerts(config: dict) -> int:
    validate_alert_config(config)
    today = datetime.now(IST).date().isoformat()
    sent = 0
    with connect(config["DATABASE_PATH"]) as db:
        subscriptions = db.execute(
            "SELECT * FROM subscriptions WHERE last_alert_date IS NULL OR last_alert_date != ?",
            (today,),
        ).fetchall()
    for subscriber in subscriptions:
        forecast = get_forecast(subscriber["latitude"], subscriber["longitude"], True)
        tomorrow = (datetime.fromisoformat(today) + timedelta(days=1)).date().isoformat()
        by_date = {day["date"]: day["rain_mm"] for day in forecast["days"]}
        if forecast["status"] != "live" or today not in by_date or tomorrow not in by_date:
            logger.warning("Weather alert skipped: forecast unavailable or incomplete.")
            continue
        rain = by_date[today] + by_date[tomorrow]
        if rain <= 20:
            continue
        # Re-check consent just before dispatch so STOP cancels a pending batch item.
        with connect(config["DATABASE_PATH"]) as db:
            if not db.execute(
                "SELECT 1 FROM subscriptions WHERE session_key=?", (subscriber["session_key"],)
            ).fetchone():
                continue
        try:
            send_payload(
                config,
                subscriber["phone"],
                {
                    "type": "template",
                    "template": {
                        "name": config["META_ALERT_TEMPLATE"],
                        "language": {"code": config["META_ALERT_LANGUAGE"]},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [{"type": "text", "text": f"{rain:.1f}"}],
                            }
                        ],
                    },
                },
            )
        except DeliveryError:
            logger.error("Weather alert delivery failed; subscription remains eligible for retry.")
            continue
        with connect(config["DATABASE_PATH"]) as db:
            db.execute(
                "UPDATE subscriptions SET last_alert_date=? WHERE session_key=?",
                (today, subscriber["session_key"]),
            )
        sent += 1
    return sent


def run_scheduler(config: dict) -> None:
    validate_alert_config(config)
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        dispatch_alerts,
        "cron",
        hour=7,
        minute=0,
        args=[config],
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
