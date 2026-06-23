/**
 * M.I.K.U. Dashboard — browser mic, MediaPipe webcam, single-voice TTS
 */

import {
  startWebcamGestures,
  stopWebcamGestures,
  isWebcamRunning,
} from "./gestures-client.js";

const API = "";

const statusBadge = document.getElementById("status-badge");
const gestureHint = document.getElementById("gesture-hint");
const voiceHint = document.getElementById("voice-hint");
const transcriptDisplay = document.getElementById("transcript-display");
const responseDisplay = document.getElementById("response-display");
const traceDisplay = document.getElementById("trace-display");
const commandInput = document.getElementById("command-input");
const sendBtn = document.getElementById("send-btn");
const videoEl = document.getElementById("webcam-video");
const canvasEl = document.getElementById("webcam-canvas");
const gestureOverlay = document.getElementById("gesture-overlay");

let lastResponse = "";
let recognition = null;
let currentAudio = null;
let isAsleep = true;
let isListening = false;
let isSpeaking = false;
let activeMode = null;

const MODE_MAP = {
  one_finger: "study",
  two_fingers: "search",
  three_fingers: "chat",
  study_mode: "study",
  search_mode: "search",
  chat_mode: "chat",
};

function setStatus(status) {
  statusBadge.textContent = status;
  statusBadge.className = "status-badge " + status;
}

function showTrace(trace) {
  if (!trace) return;
  traceDisplay.textContent = JSON.stringify(trace, null, 2);
}

async function apiPost(path, body = {}) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function stopCurrentAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
  isSpeaking = false;
}

async function playTTS(text) {
  if (!text || isAsleep) return;
  stopCurrentAudio();
  isSpeaking = true;
  setStatus("speaking");

  try {
    const res = await fetch(API + "/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudio = audio;
      await audio.play();
      await new Promise((resolve) => {
        audio.onended = () => {
          URL.revokeObjectURL(url);
          currentAudio = null;
          isSpeaking = false;
          setStatus("awake");
          resolve();
        };
        audio.onerror = () => {
          isSpeaking = false;
          setStatus("awake");
          resolve();
        };
      });
      return;
    }
  } catch (_) {}
  isSpeaking = false;
  setStatus("awake");
}

function initSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const rec = new SR();
  rec.lang = "en-US";
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  return rec;
}

async function listenWithBrowserMic(mode = null) {
  if (isAsleep) {
    responseDisplay.textContent = "MIKU is asleep. Show an open hand to wake.";
    return;
  }
  if (isListening) return;
  if (isSpeaking) stopCurrentAudio();

  if (!recognition) recognition = initSpeechRecognition();
  if (!recognition) throw new Error("Browser speech recognition not supported. Use Chrome.");

  if (mode) activeMode = mode;
  isListening = true;
  setStatus("listening");
  gestureHint.textContent = `Listening${activeMode ? ` (${activeMode} mode)` : ""}… speak now`;

  return new Promise((resolve, reject) => {
    recognition.onresult = async (event) => {
      isListening = false;
      const transcript = event.results[0][0].transcript;
      transcriptDisplay.textContent = transcript;
      setStatus("thinking");

      try {
        const data = await apiPost("/api/voice-command", {
          text: transcript,
          input_type: "voice",
          active_mode: activeMode,
        });
        responseDisplay.textContent = data.response || "—";
        lastResponse = data.response || "";
        showTrace(data.trace);
        setStatus(data.status || "awake");
        activeMode = null;
        if (data.response) await playTTS(data.response);
        resolve(data);
      } catch (e) {
        reject(e);
      }
    };

    recognition.onerror = (event) => {
      isListening = false;
      if (event.error === "no-speech") {
        responseDisplay.textContent = "I didn't catch that. Try again.";
        setStatus("awake");
        resolve({ transcript: "" });
      } else {
        reject(new Error(event.error));
      }
    };

    recognition.onend = () => {
      isListening = false;
      if (isWebcamRunning()) gestureHint.textContent = "Webcam + MediaPipe active";
    };

    recognition.start();
  });
}

async function pollStatus() {
  try {
    const data = await fetch(API + "/api/status").then((r) => r.json());
    if (!isListening && !isSpeaking && data.miku_status !== "thinking") {
      if (!isAsleep || data.miku_status === "asleep") {
        setStatus(data.miku_status || "awake");
      }
    }
    if (data.voice) {
      voiceHint.textContent = `TTS: ${data.voice.active_engine} (${data.voice.edge_voice || "Jarvis-style"})`;
    }
  } catch (_) {
    setStatus("offline");
  }
}

async function sendCommand(text) {
  if (isAsleep) {
    responseDisplay.textContent = "MIKU is asleep. Wake first.";
    return;
  }
  setStatus("thinking");
  try {
    const data = await apiPost("/api/command", { text, input_type: "text" });
    if (data.transcript) transcriptDisplay.textContent = data.transcript;
    if (data.response) {
      responseDisplay.textContent = data.response;
      lastResponse = data.response;
      await playTTS(data.response);
    }
    showTrace(data.trace);
    setStatus(data.status || "awake");
  } catch (e) {
    responseDisplay.textContent = "Error: " + e.message;
    setStatus("awake");
  }
}

async function triggerGesture(gesture) {
  if (isListening || isSpeaking) return;

  // Sleep
  if (gesture === "closed_fist") {
    stopCurrentAudio();
    isAsleep = true;
    activeMode = null;
    const data = await apiPost("/api/gesture", { gesture });
    responseDisplay.textContent = data.response || "Sleeping.";
    setStatus("asleep");
    showTrace(data.trace);
    return;
  }

  // Wake
  if (gesture === "open_hand") {
    isAsleep = false;
    const data = await apiPost("/api/gesture", { gesture });
    responseDisplay.textContent = data.response || "Awake.";
    setStatus("awake");
    showTrace(data.trace);
    await playTTS(data.response);
    return;
  }

  if (isAsleep) return;

  // Mode gestures → listen for user speech (never search the gesture name)
  const mode = MODE_MAP[gesture] || null;
  if (mode || gesture === "closed_pinch") {
    await apiPost("/api/gesture", { gesture });
    try {
      await listenWithBrowserMic(mode);
    } catch (e) {
      responseDisplay.textContent = "Mic error: " + e.message;
      setStatus("awake");
    }
  }
}

async function sendButton(action) {
  if (action === "sleep") {
    await triggerGesture("closed_fist");
    return;
  }
  if (action === "wake") {
    await triggerGesture("open_hand");
    return;
  }
  if (action === "listen" || action === "speak") {
    try {
      await listenWithBrowserMic(activeMode);
    } catch (e) {
      responseDisplay.textContent = "Mic error: " + e.message;
      setStatus("awake");
    }
    return;
  }

  if (isAsleep && action !== "wake") {
    responseDisplay.textContent = "MIKU is asleep. Click Wake first.";
    return;
  }

  const mode = MODE_MAP[action];
  if (mode) {
    activeMode = mode;
    try {
      await listenWithBrowserMic(mode);
    } catch (e) {
      responseDisplay.textContent = "Mic error: " + e.message;
    }
    return;
  }

  if (action === "thumbs_up" || action === "thumbs_down") {
    setStatus("thinking");
    const data = await apiPost("/api/command", { text: action, input_type: "button" });
    responseDisplay.textContent = data.response || "—";
    lastResponse = data.response || "";
    showTrace(data.trace);
    setStatus(data.status || "awake");
    if (data.response) await playTTS(data.response);
  }
}

document.querySelectorAll("[data-action]").forEach((btn) => {
  btn.addEventListener("click", () => sendButton(btn.dataset.action));
});

sendBtn.addEventListener("click", () => {
  const text = commandInput.value.trim();
  if (text) {
    sendCommand(text);
    commandInput.value = "";
  }
});

commandInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendBtn.click();
});

document.getElementById("start-gestures-btn").addEventListener("click", async () => {
  const ok = await startWebcamGestures({
    videoEl,
    canvasEl,
    overlayEl: gestureOverlay,
    onGesture: triggerGesture,
    onStatus: (msg) => { gestureHint.textContent = msg; },
  });
  if (!ok) gestureHint.textContent = "Could not start camera — check permissions";
});

document.getElementById("stop-gestures-btn").addEventListener("click", () => {
  stopWebcamGestures({ videoEl, overlayEl: gestureOverlay });
  gestureHint.textContent = "Camera stopped";
});

setInterval(pollStatus, 3000);
pollStatus();
setStatus("asleep");

window.addEventListener("load", () => {
  setTimeout(() => document.getElementById("start-gestures-btn").click(), 500);
});
