"""Text-to-speech — Jarvis-style British voice via edge-tts, pyttsx3 fallback."""

import asyncio
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

_lock = threading.Lock()
_speaking = False
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Jarvis-adjacent: calm British male
DEFAULT_EDGE_VOICE = "en-GB-RyanNeural"
DEFAULT_EDGE_RATE = "-5%"


def _load_voice_config() -> dict:
  config_path = DATA_DIR / "config.json"
  if config_path.exists():
    with open(config_path) as f:
      cfg = json.load(f)
    return cfg.get("voice", {})
  return {}


def synthesize_edge_tts(text: str) -> bytes | None:
  """Synthesize via edge-tts."""
  try:
    import edge_tts

    voice_cfg = _load_voice_config()
    voice = voice_cfg.get("edge_voice", DEFAULT_EDGE_VOICE)
    rate = voice_cfg.get("edge_rate", DEFAULT_EDGE_RATE)

    async def _run() -> bytes:
      communicate = edge_tts.Communicate(text, voice, rate=rate)
      with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
      await communicate.save(path)
      with open(path, "rb") as rf:
        return rf.read()

    return asyncio.run(_run())
  except Exception:
    return None


def synthesize(text: str) -> tuple[bytes, str]:
  """Return (audio_bytes, mime_type)."""
  mp3 = synthesize_edge_tts(text)
  if mp3:
    return mp3, "audio/mpeg"
  return b"", ""


def _play_bytes(audio: bytes, mime: str) -> bool:
  if not audio:
    return False
  suffix = ".mp3" if "mpeg" in mime else ".wav"
  with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
    f.write(audio)
    path = f.name
  if sys.platform == "darwin":
    subprocess.run(["afplay", path], check=False)
  else:
    subprocess.run(
      ["ffplay", "-nodisp", "-autoexit", path],
      check=False,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
    )
  return True


def _speak_pyttsx3(text: str) -> None:
  import pyttsx3

  engine = pyttsx3.init()
  engine.setProperty("rate", 165)
  # Prefer a British voice if available on macOS
  for v in engine.getProperty("voices"):
    if "daniel" in v.id.lower() or "uk" in v.id.lower() or "british" in v.name.lower():
      engine.setProperty("voice", v.id)
      break
  engine.say(text)
  engine.runAndWait()


def speak(text: str, block: bool = False) -> None:
  """Speak text — only one utterance at a time (no layering)."""

  def _do():
    global _speaking
    with _lock:
      if _speaking:
        return
      _speaking = True
    try:
      audio, mime = synthesize(text)
      if audio and _play_bytes(audio, mime):
        return
      with _lock:
        _speak_pyttsx3(text)
    finally:
      with _lock:
        _speaking = False

  if block:
    _do()
  else:
    threading.Thread(target=_do, daemon=True).start()


def get_voice_status() -> dict:
  edge_ok = False
  try:
    import edge_tts  # noqa: F401

    edge_ok = True
  except ImportError:
    pass
  voice_cfg = _load_voice_config()
  return {
    "active_engine": "edge-tts" if edge_ok else "pyttsx3",
    "edge_voice": voice_cfg.get("edge_voice", DEFAULT_EDGE_VOICE),
    "edge_tts_available": edge_ok,
  }
