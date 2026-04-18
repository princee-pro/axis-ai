"""
Voice Interface — Phase 8: Voice Interface MVP
Push-to-talk only. No background listening, no wake word.

Provides STT and TTS provider abstractions with:
- Mock providers that work out of the box for local testing
- Optional pyttsx3 TTS (system TTS engine) if installed
- Privacy defaults: raw audio deleted after processing unless retain_raw_audio=True
- Safe file storage under storage/voice_outputs/
"""
import os
import sys
import time
import uuid
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported upload MIME types
# ---------------------------------------------------------------------------
DEFAULT_ALLOWED_MIME_TYPES = [
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
    "audio/x-m4a",
    "audio/m4a",
]

# Policy: unsafe transcript patterns that must route via governance
_UNSAFE_PATTERNS = [
    "captcha", "solve the captcha", "bypass captcha",
    "log in for me", "login for me", "sign in for me",
    "fill in the password", "enter my password",
    "bypass authentication", "bypass login",
    "send email without approval", "send now without",
    "skip approval", "execute without approval",
]


# ===========================================================================
# STT — Speech-to-Text providers
# ===========================================================================

class MockSTTProvider:
    """Returns a deterministic mock transcript. No external calls."""
    name = "mock"

    def transcribe(self, audio_bytes: bytes, mime_type: str, filename: str = "") -> dict:
        # Derive a stable-ish fake transcript from filename or content hash
        hint = os.path.splitext(filename)[0] if filename else hashlib.md5(audio_bytes[:32]).hexdigest()[:8]
        transcript = f"[mock transcript from {hint}]"
        return {
            "transcript": transcript,
            "provider":   self.name,
            "language":   "en",
            "duration_ms": max(500, len(audio_bytes) // 16),  # rough estimate
        }

    @property
    def available(self) -> bool:
        return True


class LocalWhisperSTTProvider:
    """
    Optional: uses OpenAI's Whisper library (local inference, no internet).
    Install with: pip install openai-whisper
    Falls back gracefully if not installed.
    """
    name = "local_whisper"

    def __init__(self, model_size: str = "base"):
        self._model = None
        self._model_size = model_size
        self._available = False
        try:
            import whisper  # type: ignore
            self._whisper = whisper
            self._available = True
        except ImportError:
            self._whisper = None

    @property
    def available(self) -> bool:
        return self._available

    def _load_model(self):
        if self._model is None and self._whisper:
            self._model = self._whisper.load_model(self._model_size)

    def transcribe(self, audio_bytes: bytes, mime_type: str, filename: str = "") -> dict:
        if not self._available:
            raise RuntimeError("Whisper not installed. pip install openai-whisper")
        import tempfile
        self._load_model()
        # Write to a temp file for whisper
        ext = ".wav" if "wav" in mime_type else ".mp3"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
            tf.write(audio_bytes)
            tmp_path = tf.name
        try:
            t0 = time.time()
            result = self._model.transcribe(tmp_path)
            duration_ms = int((time.time() - t0) * 1000)
            return {
                "transcript": result.get("text", "").strip(),
                "provider":   self.name,
                "language":   result.get("language", "en"),
                "duration_ms": duration_ms,
            }
        finally:
            os.unlink(tmp_path)


class GroqSTTProvider:
    """
    Uses Groq API for lightning fast STT.
    """
    name = "groq"

    def __init__(self):
        self._available = False
        try:
            from groq import Groq
            if os.environ.get("GROQ_API_KEY"):
                self._client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
                self._available = True
        except ImportError:
            pass

    @property
    def available(self) -> bool:
        return self._available

    def transcribe(self, audio_bytes: bytes, mime_type: str, filename: str = "") -> dict:
        if not self._available:
            raise RuntimeError("Groq module or GROQ_API_KEY not available.")
        import tempfile
        ext = ".wav" if "wav" in mime_type else ".mp3"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
            tf.write(audio_bytes)
            tmp_path = tf.name
        try:
            t0 = time.time()
            with open(tmp_path, "rb") as f:
                file_name = filename if filename else f"audio{ext}"
                try:
                    result = self._client.audio.transcriptions.create(
                        file=(file_name, f.read()),
                        model="whisper-large-v3",
                    )
                except Exception as e:
                    logger.error(f"[VOICE] Groq STT transcription failed: {e}")
                    raise
            duration_ms = int((time.time() - t0) * 1000)
            return {
                "transcript": result.text.strip(),
                "provider":   self.name,
                "language":   "en",
                "duration_ms": duration_ms,
            }
        finally:
            os.unlink(tmp_path)


def _get_stt_provider(provider_name: str) -> object:
    """Return the appropriate STT provider, falling back to mock."""
    if provider_name == "local_whisper":
        p = LocalWhisperSTTProvider()
        if p.available:
            return p
        logger.warning("[VOICE] Whisper not installed, falling back to mock STT.")
    elif provider_name == "groq":
        p = GroqSTTProvider()
        if p.available:
            return p
        logger.warning("[VOICE] Groq not available, falling back to mock STT.")
    return MockSTTProvider()


# ===========================================================================
# TTS — Text-to-Speech providers
# ===========================================================================

class MockTTSProvider:
    """
    Writes a .txt placeholder instead of real audio.
    Useful for local tests and CI without sound hardware.
    """
    name = "mock"

    def speak(self, text: str, output_path: str) -> dict:
        # Write placeholder text file as a stand-in for audio
        txt_path = output_path.rsplit(".", 1)[0] + ".txt"
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"[MOCK TTS OUTPUT]\n{text}\n")
        size = os.path.getsize(txt_path)
        return {
            "provider":     self.name,
            "path":         txt_path,
            "content_type": "text/plain",
            "size_bytes":   size,
            "real_audio":   False,
        }

    @property
    def available(self) -> bool:
        return True


class Pyttsx3TTSProvider:
    """
    Optional: uses pyttsx3 for real OS-native TTS (works on Windows/macOS/Linux).
    Install with: pip install pyttsx3
    Falls back to mock if not installed or if audio hardware is unavailable.
    """
    name = "pyttsx3"

    def __init__(self):
        self._available = False
        try:
            import pyttsx3  # type: ignore
            # Quick availability check — init can fail on headless systems
            _eng = pyttsx3.init()
            _eng.stop()
            self._pyttsx3 = pyttsx3
            self._available = True
        except Exception:
            self._pyttsx3 = None

    @property
    def available(self) -> bool:
        return self._available

    def speak(self, text: str, output_path: str) -> dict:
        if not self._available:
            raise RuntimeError("pyttsx3 not available.")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        engine = self._pyttsx3.init()
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        return {
            "provider":     self.name,
            "path":         output_path,
            "content_type": "audio/wav",
            "size_bytes":   size,
            "real_audio":   True,
        }


def _get_tts_provider(provider_name: str) -> object:
    """Return the appropriate TTS provider, falling back to mock."""
    if provider_name == "pyttsx3":
        p = Pyttsx3TTSProvider()
        if p.available:
            return p
        logger.warning("[VOICE] pyttsx3 not available, falling back to mock TTS.")
    return MockTTSProvider()


# ===========================================================================
# Voice Interface — main integration class
# ===========================================================================

class VoiceInterface:
    """
    Phase 8 Voice Interface.
    Push-to-talk only — processes one audio clip per request.
    """

    def __init__(self, config: dict):
        voice_cfg = config.get("voice", {})

        self.enabled          = voice_cfg.get("enabled", True)
        self.max_upload_bytes = int(voice_cfg.get("max_upload_mb", 10)) * 1024 * 1024
        self.retain_raw_audio = voice_cfg.get("retain_raw_audio", False)
        self.retain_tts       = voice_cfg.get("retain_tts_outputs", True)
        self.allowed_mime     = list(voice_cfg.get("allowed_mime_types", DEFAULT_ALLOWED_MIME_TYPES))

        stt_name = voice_cfg.get("stt_provider", "mock")
        tts_name = voice_cfg.get("tts_provider", "mock")

        self._stt = _get_stt_provider(stt_name)
        self._tts = _get_tts_provider(tts_name)

        # Safe output directory
        self._output_dir = os.path.join(os.getcwd(), "storage", "voice_outputs")
        os.makedirs(self._output_dir, exist_ok=True)

    # -----------------------------------------------------------------------
    # STT
    # -----------------------------------------------------------------------
    def transcribe(self, audio_bytes: bytes, mime_type: str, filename: str = "") -> dict:
        """
        Transcribe uploaded audio to text.
        Raw audio is never persisted by default (retain_raw_audio=False).
        """
        self._validate_upload(audio_bytes, mime_type)

        tmp_path: Optional[str] = None
        if self.retain_raw_audio:
            safe_name = f"{uuid.uuid4().hex}_{_sanitize_filename(filename or 'upload')}"
            tmp_path  = os.path.join(self._output_dir, "raw", safe_name)
            os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)

        result = self._stt.transcribe(audio_bytes, mime_type, filename)

        # If we wrote a raw file but retain is off, delete it now
        if tmp_path and not self.retain_raw_audio and os.path.exists(tmp_path):
            os.unlink(tmp_path)

        result["retained_raw"] = bool(self.retain_raw_audio and tmp_path)
        return result

    # -----------------------------------------------------------------------
    # TTS
    # -----------------------------------------------------------------------
    def speak(self, text: str, fmt: str = "wav") -> dict:
        """
        Generate TTS audio from text. Returns file metadata, not raw bytes.
        """
        if not text or not text.strip():
            raise ValueError("Text for TTS may not be empty.")
        if len(text) > 4096:
            raise ValueError("Text for TTS exceeds 4096 character limit.")

        safe_fmt  = "wav" if fmt not in ("wav", "mp3") else fmt
        filename  = f"{uuid.uuid4().hex}.{safe_fmt}"
        out_path  = os.path.join(self._output_dir, filename)

        result = self._tts.speak(text.strip(), out_path)

        if not self.retain_tts and os.path.exists(result["path"]):
            os.unlink(result["path"])
            result["path"] = None

        return result

    # -----------------------------------------------------------------------
    # Capabilities
    # -----------------------------------------------------------------------
    def get_capabilities(self) -> dict:
        return {
            "voice_enabled":        self.enabled,
            "stt_available":        self._stt.available,
            "stt_provider":         self._stt.name,
            "tts_available":        self._tts.available,
            "tts_provider":         self._tts.name,
            "max_upload_mb":        self.max_upload_bytes // (1024 * 1024),
            "allowed_mime_types":   self.allowed_mime,
            "retain_raw_audio":     self.retain_raw_audio,
            "push_to_talk_only":    True,
            "wake_word_enabled":    False,
            "background_listening": False,
        }

    # -----------------------------------------------------------------------
    # Safety screening
    # -----------------------------------------------------------------------
    @staticmethod
    def screen_transcript(transcript: str) -> dict:
        """
        Check transcript for patterns that must not bypass governance.
        Returns {safe: bool, warning: str|None}
        """
        lower = transcript.lower()
        for pattern in _UNSAFE_PATTERNS:
            if pattern in lower:
                return {
                    "safe": False,
                    "warning": (
                        f"Transcript matched unsafe pattern '{pattern}'. "
                        "This request will be routed through the Jarvis governance and "
                        "approval queue — no direct execution will occur."
                    ),
                }
        return {"safe": True, "warning": None}

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _validate_upload(self, audio_bytes: bytes, mime_type: str):
        if not self.enabled:
            raise RuntimeError("Voice interface is disabled in config (voice.enabled: false).")
        if len(audio_bytes) == 0:
            raise ValueError("Empty audio upload.")
        if len(audio_bytes) > self.max_upload_bytes:
            raise ValueError(
                f"Upload too large: {len(audio_bytes) // 1024}KB exceeds "
                f"{self.max_upload_bytes // (1024*1024)}MB limit."
            )
        # Normalize mime — browsers may send audio/mp3 or audio/mpeg interchangeably
        norm_mime = mime_type.split(";")[0].strip().lower()
        if norm_mime and norm_mime not in [m.lower() for m in self.allowed_mime]:
            raise ValueError(
                f"Unsupported audio type '{norm_mime}'. "
                f"Allowed: {', '.join(self.allowed_mime)}"
            )


def _sanitize_filename(name: str) -> str:
    """Remove path separators and exotic chars from filename."""
    import re
    name = os.path.basename(name)
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:64] or "upload"
