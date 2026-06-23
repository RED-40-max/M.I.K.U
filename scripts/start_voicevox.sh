#!/usr/bin/env bash
# Start VOICEVOX ENGINE for Miku-style TTS (四国めたん あまあま)
# Download VOICEVOX from https://voicevox.hiroshiba.jp/ if not installed.

set -e

VOICEVOX_APP="/Applications/VOICEVOX.app/Contents/MacOS/VOICEVOX"
ENGINE_BIN=""

if [ -x "$VOICEVOX_APP" ]; then
  echo "Starting VOICEVOX ENGINE on http://127.0.0.1:50021 ..."
  open -a VOICEVOX --args --host 127.0.0.1 --port 50021 2>/dev/null || true
  echo "VOICEVOX launched. Enable engine in the app if needed."
else
  echo "VOICEVOX not found at $VOICEVOX_APP"
  echo "Install from: https://voicevox.hiroshiba.jp/"
  echo "Fallback TTS: edge-tts (ja-JP-MayuNeural) will be used automatically."
fi
