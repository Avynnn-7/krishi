"""Text-to-Speech synthesis using Google Cloud TTS or gTTS fallback.

Provides Hindi audio narration of bot advisory results so farmers
who find reading difficult can *listen* to their recommendations.

Priority order:
  1. Google Cloud TTS (if GOOGLE_APPLICATION_CREDENTIALS is set) – higher quality
  2. gTTS (pip install gTTS) – free, no credentials needed
  3. Returns None when neither is available

The module is intentionally lazy-loaded and tolerant of missing dependencies
so the bot runs fine without TTS configured.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────────

_CACHE_DIR: Path | None = None


def _get_cache_dir() -> Path:
    global _CACHE_DIR
    if _CACHE_DIR is None:
        _CACHE_DIR = Path(tempfile.gettempdir()) / "jalkhadd_tts"
        _CACHE_DIR.mkdir(exist_ok=True)
    return _CACHE_DIR


def _cache_key(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ── Public API ───────────────────────────────────────────────────────────────


def synthesize_hindi(text: str, *, voice: str = "hi-IN-Wavenet-A") -> bytes | None:
    """Synthesize Hindi text to OGG/Opus audio bytes.

    Args:
        text: Hindi text to speak (plain text, no markdown).
        voice: Google Cloud voice name (ignored for gTTS fallback).

    Returns:
        OGG/Opus audio bytes ready to send via WhatsApp, or None
        if no TTS backend is available.
    """
    if not text or not text.strip():
        return None

    # Check cache
    cache_path = _get_cache_dir() / f"{_cache_key(text)}.ogg"
    if cache_path.exists():
        return cache_path.read_bytes()

    audio = _try_google_tts(text, voice)
    if audio is None:
        audio = _try_gtts(text)
    if audio is None:
        logger.warning("No TTS backend available – skipping voice narration.")
        return None

    # Cache for reuse
    try:
        cache_path.write_bytes(audio)
    except OSError:
        pass
    return audio


def _try_google_tts(text: str, voice: str) -> bytes | None:
    """Attempt synthesis via Google Cloud Text-to-Speech."""
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return None
    try:
        from google.cloud import texttospeech  # type: ignore[import-untyped]
    except ImportError:
        return None

    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="hi-IN",
            name=voice,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
            speaking_rate=0.95,  # Slightly slower for rural listeners
        )
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )
        logger.info("Google Cloud TTS: synthesized %d bytes", len(response.audio_content))
        return response.audio_content
    except Exception:
        logger.exception("Google Cloud TTS failed")
        return None


def _try_gtts(text: str) -> bytes | None:
    """Fallback: use gTTS (free, no credentials)."""
    try:
        from gtts import gTTS  # type: ignore[import-untyped]
    except ImportError:
        return None

    try:
        tts = gTTS(text=text, lang="hi", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        mp3_bytes = buf.getvalue()

        # Convert MP3 → OGG/Opus for WhatsApp compatibility using pydub if available
        ogg_bytes = _mp3_to_ogg(mp3_bytes)
        if ogg_bytes is not None:
            logger.info("gTTS + pydub: synthesized %d bytes (OGG)", len(ogg_bytes))
            return ogg_bytes

        # If pydub is not available, return MP3 – WhatsApp also accepts MP3 audio
        logger.info("gTTS: synthesized %d bytes (MP3 fallback)", len(mp3_bytes))
        return mp3_bytes
    except Exception:
        logger.exception("gTTS synthesis failed")
        return None


def _mp3_to_ogg(mp3_bytes: bytes) -> bytes | None:
    """Convert MP3 bytes to OGG/Opus using pydub + ffmpeg."""
    try:
        from pydub import AudioSegment  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
        buf = io.BytesIO()
        audio.export(buf, format="ogg", codec="libopus", parameters=["-b:a", "32k"])
        return buf.getvalue()
    except Exception:
        logger.debug("pydub OGG conversion failed – will use MP3", exc_info=True)
        return None


def is_available() -> bool:
    """Check whether any TTS backend can be used."""
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            from google.cloud import texttospeech  # noqa: F401
            return True
        except ImportError:
            pass
    try:
        from gtts import gTTS  # noqa: F401
        return True
    except ImportError:
        pass
    return False
