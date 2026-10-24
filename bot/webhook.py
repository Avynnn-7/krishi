import hashlib
import hmac
import json
import re
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, request
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from bot.meta_api import DeliveryError, send_reply
from bot.state_machine import handle_message
from storage import connect

webhook_bp = Blueprint("webhook", __name__)


def process_message(message_id: str, phone: str, text: str) -> dict:
    config = current_app.config
    with connect(config["DATABASE_PATH"]) as db:
        db.execute("BEGIN IMMEDIATE")
        cached = db.execute(
            "SELECT reply, sent FROM inbox WHERE message_id = ?", (message_id,)
        ).fetchone()
        if cached:
            return {"reply": json.loads(cached["reply"]), "sent": bool(cached["sent"])}
        reply = handle_message(
            db,
            phone,
            text,
            config["SECRET_KEY"],
            config["DATA_DIR"],
            config["PUBLIC_BASE_URL"],
            config["WEATHER_ENABLED"],
            alerts_enabled=bool(
                message_id.startswith("meta:")
                and config.get("META_ALERT_TEMPLATE")
                and config.get("META_ACCESS_TOKEN")
                and config.get("META_PHONE_NUMBER_ID")
                and config["WEATHER_ENABLED"]
            ),
            real_phone=phone,
        )
        db.execute(
            "INSERT INTO inbox (message_id, reply, created_at) VALUES (?, ?, ?)",
            (
                message_id,
                json.dumps(reply, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return {"reply": reply, "sent": False}


@webhook_bp.route("/webhook/whatsapp", methods=["GET", "POST"])
def meta_webhook():
    config = current_app.config
    if request.method == "GET":
        token = config.get("META_VERIFY_TOKEN")
        if not token:
            abort(503, "Meta verification is not configured.")
        if request.args.get("hub.mode") != "subscribe" or not hmac.compare_digest(
            request.args.get("hub.verify_token", ""), token
        ):
            abort(403)
        return request.args.get("hub.challenge", ""), 200, {"Content-Type": "text/plain"}
    secret = config.get("META_APP_SECRET")
    if not secret or not config.get("META_ACCESS_TOKEN") or not config.get("META_PHONE_NUMBER_ID"):
        abort(503, "WhatsApp credentials are not configured.")
    signature = (
        "sha256=" + hmac.new(secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(signature, request.headers.get("X-Hub-Signature-256", "")):
        abort(403)
    payload = request.get_json()
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        abort(400, "Invalid Meta payload.")
    try:
        messages = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change["value"]
                if (
                    value.get("messages")
                    and value.get("metadata", {}).get("phone_number_id")
                    != config["META_PHONE_NUMBER_ID"]
                ):
                    abort(400, "Unexpected recipient.")
                messages.extend(value.get("messages", []))
        for message in messages:
            if (
                not isinstance(message, dict)
                or not re.fullmatch(r"\d{8,15}", message.get("from", ""))
                or not message.get("id")
            ):
                abort(400, "Invalid inbound message.")
            phone, message_id = message["from"], f"meta:{message['id']}"
            text = message.get("text", {}).get("body") if message.get("type") == "text" else None
            if not isinstance(text, str):
                send_reply(
                    config, phone, {"text": "अभी केवल लिखित संदेश स्वीकार हैं। कृपया अंक या पाठ भेजें।"}
                )
                continue
            if len(text) > 2000:
                abort(400, "Message too long.")
            result = process_message(message_id, phone, text)
            if not result["sent"]:
                send_reply(config, phone, result["reply"])
                with connect(config["DATABASE_PATH"]) as db:
                    db.execute("UPDATE inbox SET sent=1 WHERE message_id=?", (message_id,))
    except (KeyError, TypeError, AttributeError):
        abort(400, "Malformed Meta message.")
    except DeliveryError:
        current_app.logger.error("Meta delivery failed; persisted response will be retried.")
        abort(502, "Delivery failed. Retry this webhook.")
    return {"status": "ok"}


@webhook_bp.post("/webhook/twilio")
def twilio_webhook():
    config = current_app.config
    if not config.get("TWILIO_AUTH_TOKEN") or not config.get("TWILIO_WEBHOOK_URL"):
        abort(503, "Twilio sandbox is not configured.")
    valid = RequestValidator(config["TWILIO_AUTH_TOKEN"]).validate(
        config["TWILIO_WEBHOOK_URL"], request.form, request.headers.get("X-Twilio-Signature", "")
    )
    if not valid:
        abort(403)
    phone = request.form.get("From", "").removeprefix("whatsapp:").removeprefix("+")
    message_id, body = request.form.get("MessageSid"), request.form.get("Body", "")
    if not re.fullmatch(r"\d{8,15}", phone) or not message_id or len(body) > 2000:
        abort(400, "Invalid Twilio message.")
    result = process_message(f"twilio:{message_id}", phone, body)
    response = MessagingResponse()
    msg = response.message(result["reply"]["text"])
    if result["reply"].get("document"):
        msg.media(result["reply"]["document"])
    return str(response), 200, {"Content-Type": "application/xml"}
