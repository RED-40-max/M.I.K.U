"""FastAPI server — MIKU Desktop Assistant API."""

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.graph import run_agent
from backend.gestures import (
  get_current_gesture,
  is_running as gestures_running,
  start_detection,
  stop_detection,
)
from backend.logger import build_trace, get_recent_traces
from backend.memory import load_memory, set_preference
from backend.tts import get_voice_status, speak, synthesize
from backend.voice import check_mic_available, get_last_transcript, is_listening, listen_once

app = FastAPI(title="MIKU Desktop Assistant", version="1.0.0")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"],
)

# Global MIKU status
_miku_status = "asleep"


class CommandRequest(BaseModel):
  text: str = ""
  input_type: str = "text"  # text | voice | button | gesture
  gesture: str | None = None
  should_speak: bool = False


class GestureRequest(BaseModel):
  gesture: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/status")
def get_status():
  voice = get_voice_status()
  return {
    "miku_status": _miku_status,
    "gesture": get_current_gesture(),
    "gestures_active": gestures_running(),
    "listening": is_listening(),
    "last_transcript": get_last_transcript(),
    "mic_available": check_mic_available(),
    "voice": voice,
  }


@app.post("/api/command")
def post_command(req: CommandRequest):
  """Process a text, button, or gesture command through the LangGraph agent."""
  global _miku_status

  _miku_status = "thinking"
  try:
    result = run_agent(
      raw_input=req.text,
      input_type=req.input_type,
      gesture=req.gesture,
      transcript=req.text,
      should_speak=req.should_speak,
    )
    _miku_status = result.get("miku_status", "awake")

    if req.should_speak and result.get("response"):
      speak(result["response"])

    return {
      "status": _miku_status,
      "response": result.get("response", ""),
      "transcript": result.get("transcript", req.text),
      "intent": result.get("intent", ""),
      "trace": build_trace(result),
    }
  except Exception as e:
    _miku_status = "awake"
    raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/listen")
def post_listen():
  """Capture voice via server mic and run through agent."""
  global _miku_status

  _miku_status = "listening"
  try:
    transcript = listen_once()
  except RuntimeError as e:
    _miku_status = "awake"
    raise HTTPException(status_code=503, detail=str(e)) from e

  if not transcript:
    _miku_status = "awake"
    return {
      "status": "awake",
      "transcript": "",
      "response": "I didn't catch that. Please try again.",
      "trace": None,
    }

  _miku_status = "thinking"
  result = run_agent(
    raw_input=transcript,
    input_type="voice",
    transcript=transcript,
  )
  _miku_status = result.get("miku_status", "awake")

  return {
    "status": _miku_status,
    "transcript": transcript,
    "response": result.get("response", ""),
    "intent": result.get("intent", ""),
    "trace": build_trace(result),
  }


@app.post("/api/gesture")
def post_gesture(req: GestureRequest):
  """Handle a detected gesture — mode changes only, no tool execution from gesture name."""
  global _miku_status

  gesture = req.gesture

  if gesture == "closed_fist":
    _miku_status = "asleep"
    result = run_agent(raw_input=gesture, input_type="gesture", gesture=gesture)
    return {
      "status": "asleep",
      "gesture": gesture,
      "response": result.get("response", ""),
      "trace": build_trace(result),
      "action": "sleep",
    }

  if gesture == "open_hand":
    _miku_status = "awake"
    result = run_agent(raw_input=gesture, input_type="gesture", gesture=gesture)
    return {
      "status": "awake",
      "gesture": gesture,
      "response": result.get("response", ""),
      "trace": build_trace(result),
      "action": "wake",
    }

  # Mode + listen gestures — frontend handles mic capture
  mode_map = {
    "one_finger": "study",
    "two_fingers": "search",
    "three_fingers": "chat",
    "closed_pinch": None,
  }
  mode = mode_map.get(gesture)
  if mode:
    set_preference("active_mode", mode)

  result = run_agent(raw_input=gesture, input_type="gesture", gesture=gesture)
  _miku_status = "listening"
  return {
    "status": "listening",
    "gesture": gesture,
    "response": result.get("response", ""),
    "trace": build_trace(result),
    "action": "listen",
    "active_mode": mode,
  }


@app.post("/api/gestures/start")
def start_gestures():
  """Start MediaPipe webcam gesture detection."""
  started = start_detection()
  return {"started": started, "active": gestures_running()}


@app.post("/api/gestures/stop")
def stop_gestures():
  stop_detection()
  return {"active": False}


@app.get("/api/traces")
def get_traces(limit: int = 20):
  return {"traces": get_recent_traces(limit)}


@app.get("/api/memory")
def get_memory():
  return load_memory()


@app.post("/api/speak")
def post_speak(req: CommandRequest):
  """Speak the provided text via TTS."""
  global _miku_status
  _miku_status = "speaking"
  speak(req.text)
  _miku_status = "awake"
  return {"spoken": req.text}


@app.post("/api/tts")
def post_tts(req: CommandRequest):
  """Return synthesized audio for browser playback (VOICEVOX / edge-tts)."""
  audio, mime = synthesize(req.text)
  if not audio:
    raise HTTPException(status_code=503, detail="No TTS engine available")
  return Response(content=audio, media_type=mime)


class VoiceTranscriptRequest(BaseModel):
  text: str
  input_type: str = "voice"
  active_mode: str | None = None


@app.post("/api/voice-command")
def post_voice_command(req: VoiceTranscriptRequest):
  """Process a browser-captured voice transcript through the agent."""
  global _miku_status

  transcript = req.text.strip()
  if not transcript:
    return {
      "status": "awake",
      "transcript": "",
      "response": "I didn't catch that. Please try again.",
      "trace": None,
    }

  _miku_status = "thinking"
  result = run_agent(
    raw_input=transcript,
    input_type=req.input_type,
    transcript=transcript,
    active_mode=req.active_mode,
  )
  _miku_status = result.get("miku_status", "awake")

  return {
    "status": _miku_status,
    "transcript": transcript,
    "response": result.get("response", ""),
    "intent": result.get("intent", ""),
    "trace": build_trace(result),
  }


# Serve frontend
FRONTEND_DIR = ROOT / "frontend"
if FRONTEND_DIR.exists():
  app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_dashboard():
  index = FRONTEND_DIR / "index.html"
  if index.exists():
    return FileResponse(str(index))
  return {"message": "MIKU backend running. Place frontend in /frontend."}


if __name__ == "__main__":
  import uvicorn

  config_path = ROOT / "data" / "config.json"
  with open(config_path) as f:
    cfg = json.load(f)
  uvicorn.run(
    "backend.main:app",
    host=cfg.get("server_host", "127.0.0.1"),
    port=cfg.get("server_port", 8000),
    reload=True,
  )
