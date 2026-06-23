"""Voice input — browser-first with server SpeechRecognition / whisper fallback."""

import threading
from typing import Callable

_listening = False
_last_transcript = ""
_mic_available: bool | None = None


def get_last_transcript() -> str:
  return _last_transcript


def is_listening() -> bool:
  return _listening


def check_mic_available() -> bool:
  """Probe whether server-side microphone capture is available."""
  global _mic_available
  if _mic_available is not None:
    return _mic_available
  try:
    import speech_recognition as sr
  except ImportError:
    _mic_available = False
    return False
  try:
    with sr.Microphone() as source:
      pass
    _mic_available = True
  except Exception:
    _mic_available = False
  return _mic_available


def listen_once(timeout: int = 5, phrase_limit: int = 8) -> str:
  """
  Capture one voice utterance and return transcript.
  Uses SpeechRecognition (Google free API) or faster-whisper offline fallback.
  """
  global _listening, _last_transcript

  _listening = True
  try:
    import speech_recognition as sr
  except ImportError as e:
    raise RuntimeError(
      "Server mic unavailable. Install: pip install SpeechRecognition pyaudio "
      "— or use the Listen button which uses your browser microphone."
    ) from e

  try:
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    with sr.Microphone() as source:
      recognizer.adjust_for_ambient_noise(source, duration=0.2)
      audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)

    try:
      text = recognizer.recognize_google(audio)
      _last_transcript = text
      return text
    except sr.UnknownValueError:
      _last_transcript = ""
      return ""
    except sr.RequestError:
      return _whisper_fallback(audio)
  except sr.WaitTimeoutError:
    _last_transcript = ""
    return ""
  except OSError as e:
    raise RuntimeError(
      f"Microphone not accessible: {e}. "
      "Grant mic permission or use browser Listen (recommended)."
    ) from e
  finally:
    _listening = False


def _whisper_fallback(audio) -> str:
  """Try faster-whisper if available."""
  global _last_transcript
  try:
    import io
    import tempfile

    from faster_whisper import WhisperModel

    wav_data = io.BytesIO(audio.get_wav_data())
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
      f.write(wav_data.read())
      path = f.name

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(path)
    text = " ".join(s.text for s in segments).strip()
    _last_transcript = text
    return text
  except Exception:
    _last_transcript = ""
    return ""


def listen_async(callback: Callable[[str], None], timeout: int = 5) -> None:
  """Start listening in a background thread."""

  def _run():
    try:
      result = listen_once(timeout=timeout)
      callback(result)
    except Exception as e:
      callback("")
      raise e

  threading.Thread(target=_run, daemon=True).start()
