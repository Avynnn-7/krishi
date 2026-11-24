
"""
WhatsApp Web Bot for Krishi Jal-Khadd
======================================
Connects the Jal-Khadd advisory state machine directly to WhatsApp Web
using neonize (no Meta Business API or Twilio required).

Usage:
    1.  pip install neonize
    2.  python whatsapp_bot.py
    3.  Scan the QR code with WhatsApp on your phone (or open qr_code.png).
    4.  Farmers message this number and get the full advisory flow.

The bot reuses the SAME state machine, formatter, and engine that the
website and Meta/Twilio webhooks use — so behaviour is identical.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# ── Fix Windows console encoding for QR code display ──────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Project root & environment ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# Trust OS certificate store (same as app.py)
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

# ── neonize imports ────────────────────────────────────────────────────
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv, PairStatusEv
from neonize.utils.message import extract_text
import segno

# ── Krishi bot internals ───────────────────────────────────────────────
from bot.state_machine import handle_message
from engine.service import load_catalog, load_blocks
from engine.stcr import load_profiles
from engine.irrigation import load_water_data
from storage import connect, initialize

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("whatsapp_bot")

# ── Configuration (mirrors create_app() in app.py) ─────────────────────
CONFIG = {
    "SECRET_KEY": os.getenv("SECRET_KEY", "dev-secret-change-me"),
    "DATABASE_PATH": os.getenv("DATABASE_PATH", str(ROOT / "instance" / "jalkhadd.db")),
    "DATA_DIR": ROOT / "data",
    "PUBLIC_BASE_URL": os.getenv("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/"),
    "WEATHER_ENABLED": os.getenv("WEATHER_ENABLED", "true").lower() == "true",
}

# Session DB for neonize (stores WhatsApp Web credentials after first QR scan)
SESSION_DB = str(ROOT / "instance" / "whatsapp_session.db")


def bootstrap():
    """Validate reference data at startup (same checks as Flask app)."""
    (ROOT / "instance").mkdir(exist_ok=True)
    initialize(CONFIG["DATABASE_PATH"])
    load_catalog(CONFIG["DATA_DIR"])
    load_profiles(CONFIG["DATA_DIR"])
    load_water_data(CONFIG["DATA_DIR"])
    logger.info("Reference data loaded successfully.")


def phone_from_jid(jid) -> str:
    """Extract a numeric phone string from a neonize JID object.

    neonize JIDs look like '919876543210@s.whatsapp.net'.
    The state machine expects just the digits.
    """
    raw = str(jid)
    # Strip the @s.whatsapp.net / @g.us suffix and any non-digit chars
    return re.sub(r"[^\d]", "", raw.split("@")[0])


def build_reply_text(reply: dict) -> str:
    """Compose the text body to send back, including document links."""
    text = reply.get("text", "")
    if reply.get("document"):
        text += f"\n\n📎 PDF: {reply['document']}"
    return text


# ── Create neonize client ──────────────────────────────────────────────
client = NewClient(SESSION_DB)

QR_IMAGE_PATH = ROOT / "instance" / "qr_code.png"


@client.qr
def on_qr(_client: NewClient, data_qr: bytes):
    """Save QR as a PNG image and print a notice (avoids Unicode encoding errors on Windows)."""
    qr = segno.make_qr(data_qr)
    qr.save(str(QR_IMAGE_PATH), scale=8, border=2)
    logger.info(
        "📱 QR CODE SAVED → %s\n"
        "   Open this image file and scan it with WhatsApp on your phone.\n"
        "   (Linked Devices → Link a Device)",
        QR_IMAGE_PATH,
    )
    # Also try terminal display (may fail on some Windows consoles)
    try:
        qr.terminal(compact=True)
    except (UnicodeEncodeError, OSError):
        pass


@client.event(ConnectedEv)
def on_connected(_client: NewClient, _event: ConnectedEv):
    logger.info("✅ WhatsApp Web connected!  Bot is live.")


@client.event(PairStatusEv)
def on_pair_status(_client: NewClient, event: PairStatusEv):
    logger.info("Pair status: %s", event)


@client.event(MessageEv)
def on_message(_client: NewClient, event: MessageEv):
    """Handle every incoming WhatsApp message through the Jal-Khadd state machine."""

    # ── Extract text ───────────────────────────────────────────────────
    text = extract_text(event.Message)
    if not text:
        return  # Ignore non-text (images, stickers, etc.)

    # ── Ignore messages sent by the bot itself ─────────────────────────
    if event.Info.MessageSource.IsFromMe:
        return

    # ── Ignore group messages (optional — remove if you want group support)
    if event.Info.MessageSource.IsGroup:
        return

    sender_jid = event.Info.MessageSource.Sender
    phone = phone_from_jid(sender_jid)
    message_id = event.Info.ID

    if not phone or len(text) > 2000:
        return

    logger.info("📩 %s: %s", phone, text[:120])

    # ── Deduplication: skip if we already processed this message ───────
    with connect(CONFIG["DATABASE_PATH"]) as db:
        neonize_msg_id = f"neonize:{message_id}"
        cached = db.execute(
            "SELECT reply, sent FROM inbox WHERE message_id = ?", (neonize_msg_id,)
        ).fetchone()
        if cached:
            if not cached["sent"]:
                reply = json.loads(cached["reply"])
                _send_wa(sender_jid, reply)
                db.execute("UPDATE inbox SET sent=1 WHERE message_id=?", (neonize_msg_id,))
            return

    # ── Run the Jal-Khadd state machine ────────────────────────────────
    try:
        with connect(CONFIG["DATABASE_PATH"]) as db:
            db.execute("BEGIN IMMEDIATE")
            reply = handle_message(
                db,
                phone,
                text,
                CONFIG["SECRET_KEY"],
                CONFIG["DATA_DIR"],
                CONFIG["PUBLIC_BASE_URL"],
                CONFIG["WEATHER_ENABLED"],
                alerts_enabled=False,       # no Meta template alerts via neonize
                real_phone=phone,
            )
            # Cache the reply (strip binary audio for storage)
            reply_for_cache = {k: v for k, v in reply.items() if k != "audio"}
            db.execute(
                "INSERT INTO inbox (message_id, reply, created_at) VALUES (?, ?, ?)",
                (
                    neonize_msg_id,
                    json.dumps(reply_for_cache, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    except Exception:
        logger.exception("State-machine error for %s", phone)
        _send_wa(sender_jid, {"text": "⚠️ कुछ गलत हो गया। कृपया फिर से कोशिश करें।"})
        return

    # ── Send the reply ─────────────────────────────────────────────────
    _send_wa(sender_jid, reply)

    # Mark as sent
    with connect(CONFIG["DATABASE_PATH"]) as db:
        db.execute("UPDATE inbox SET sent=1 WHERE message_id=?", (neonize_msg_id,))

    logger.info("📤 Replied to %s (step=%s)", phone, reply.get("step", "?"))


def _send_wa(jid, reply: dict):
    """Send a text reply (and optionally a document link) back via neonize."""
    text = build_reply_text(reply)
    if text:
        try:
            client.send_message(jid, text)
        except Exception:
            logger.exception("Failed to send message to %s", jid)


# ── Entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🚀 Starting Krishi Jal-Khadd WhatsApp Bot (neonize)…")
    bootstrap()
    logger.info("Connecting to WhatsApp Web — scan the QR code if prompted…")
    client.connect()
