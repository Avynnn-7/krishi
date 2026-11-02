import hashlib
import hmac
import io
import logging
import os

import requests


logger = logging.getLogger(__name__)


class DeliveryError(RuntimeError):
    pass


def send_payload(config: dict, phone: str, content: dict) -> None:
    required = ("META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID", "META_GRAPH_VERSION")
    if not all(config.get(key) for key in required):
        raise DeliveryError("Meta transport is not configured.")
    try:
        response = requests.post(
            f"https://graph.facebook.com/{config['META_GRAPH_VERSION']}/{config['META_PHONE_NUMBER_ID']}/messages",
            headers={"Authorization": f"Bearer {config['META_ACCESS_TOKEN']}"},
            json={"messaging_product": "whatsapp", "to": phone, **content},
            timeout=(3, 10),
        )
        response.raise_for_status()
        if not response.json().get("messages"):
            raise DeliveryError("Meta did not acknowledge the outgoing message.")
    except (requests.RequestException, ValueError) as exc:
        raise DeliveryError("WhatsApp delivery failed; retry is required.") from exc


def _upload_media(config: dict, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str | None:
    """Upload audio bytes to WhatsApp media API and return the media ID."""
    required = ("META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID", "META_GRAPH_VERSION")
    if not all(config.get(key) for key in required):
        return None
    try:
        response = requests.post(
            f"https://graph.facebook.com/{config['META_GRAPH_VERSION']}/{config['META_PHONE_NUMBER_ID']}/media",
            headers={"Authorization": f"Bearer {config['META_ACCESS_TOKEN']}"},
            files={"file": ("narration.ogg", io.BytesIO(audio_bytes), mime_type)},
            data={"messaging_product": "whatsapp", "type": mime_type},
            timeout=(5, 30),
        )
        response.raise_for_status()
        media_id = response.json().get("id")
        if media_id:
            logger.info("Uploaded TTS audio: media_id=%s", media_id)
        return media_id
    except Exception:
        logger.exception("Failed to upload TTS audio to WhatsApp")
        return None


def send_reply(config: dict, phone: str, reply: dict) -> None:
    if reply.get("document"):
        content = {
            "type": "document",
            "document": {
                "link": reply["document"],
                "caption": reply["text"],
                "filename": "jal-khadd.pdf",
            },
        }
    else:
        content = {"type": "text", "text": {"body": reply["text"]}}
    send_payload(config, phone, content)

    # ── Voice narration (optional) ────────────────────────────────────────
    # If the reply contains TTS audio bytes, upload and send as voice note
    audio_bytes = reply.get("audio")
    if audio_bytes and isinstance(audio_bytes, bytes):
        mime = "audio/ogg" if audio_bytes[:4] == b"OggS" else "audio/mpeg"
        media_id = _upload_media(config, audio_bytes, mime)
        if media_id:
            try:
                send_payload(config, phone, {
                    "type": "audio",
                    "audio": {"id": media_id},
                })
                logger.info("Sent voice narration to %s", phone)
            except DeliveryError:
                logger.warning("Voice narration delivery failed for %s (text was sent)", phone)
