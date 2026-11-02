"""Server-side audio transcription using faster-whisper (CTranslate2).

Provides Hindi + English speech-to-text for:
 - Web UI audio recordings (via /api/voice-transcribe)
 - WhatsApp voice notes (via webhook)

Uses the 'base' model by default (~74 MB) which handles Hindi well
and runs comfortably on a 2-core CPU.  Override the model size with
the WHISPER_MODEL env var (e.g. "small", "medium", "large-v3").
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded model singleton (thread-safe).
_model = None
_model_lock = threading.Lock()


def _get_model():
    """Return a cached WhisperModel instance, loading it once on first call."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper is not installed.  "
                "Run:  pip install faster-whisper"
            )
        model_size = os.getenv("WHISPER_MODEL", "base")
        cache_dir = os.getenv("WHISPER_CACHE_DIR", None)
        logger.info("Loading Whisper model '%s' (this may download ~74 MB on first run)…", model_size)
        _model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=cache_dir,
        )
        logger.info("Whisper model '%s' loaded.", model_size)
        return _model


def transcribe_audio(audio_bytes: bytes, language: str | None = "hi") -> dict:
    """Transcribe raw audio bytes to text.

    Args:
        audio_bytes: Audio data in any ffmpeg-supported format
                     (wav, ogg, webm, mp3, m4a, etc.).
        language: ISO 639-1 language hint.  Defaults to "hi" (Hindi).
                  Pass None to let Whisper auto-detect.

    Returns:
        dict with keys:
            text (str):       Full transcription text.
            language (str):   Detected/used language code.
            segments (list):  List of {start, end, text} segment dicts.
            confidence (float): Average log-probability (higher = better).
    """
    if not audio_bytes:
        raise ValueError("Empty audio data.")

    model = _get_model()

    # faster-whisper accepts a file path or a BinaryIO.
    # Write to a temp file so ffmpeg (used internally) can seek.
    suffix = ".webm"  # default; ffmpeg auto-detects format from content
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments_gen, info = model.transcribe(
            tmp_path,
            language=language,
            beam_size=5,
            best_of=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=300,
            ),
        )

        segments = []
        full_text_parts = []
        total_logprob = 0.0
        n_tokens = 0

        for seg in segments_gen:
            segments.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())
            total_logprob += seg.avg_log_prob
            n_tokens += 1

        text = " ".join(full_text_parts).strip()
        avg_confidence = total_logprob / max(n_tokens, 1)

        return {
            "text": text,
            "language": info.language,
            "segments": segments,
            "confidence": round(avg_confidence, 4),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def is_available() -> bool:
    """Check whether the transcription backend can be loaded."""
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        return True
    except ImportError:
        return False
