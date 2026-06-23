/**
 * Browser-side MediaPipe hand tracking — low-latency webcam preview + gesture detection.
 */

const TIP_IDS = [4, 8, 12, 16, 20];
const PIP_IDS = [3, 6, 10, 14, 18];

let handLandmarker = null;
let videoStream = null;
let animFrameId = null;
let lastGesture = null;
let stableCount = 0;
let running = false;
let lastTriggerTime = 0;

const GESTURE_LABELS = {
  open_hand: "✋ Open Hand — Wake",
  closed_fist: "✊ Closed Fist — Sleep",
  closed_pinch: "🤏 Pinch — Listen / Speak",
  one_finger: "☝️ Study Mode (then speak)",
  two_fingers: "✌️ Search Mode (then speak)",
  three_fingers: "🤟 Chat Mode (then speak)",
};

function countExtendedFingers(landmarks) {
  let count = 0;
  if (landmarks[4].x < landmarks[3].x) count += 1;
  for (let i = 1; i < 5; i++) {
    if (landmarks[TIP_IDS[i]].y < landmarks[PIP_IDS[i]].y) count += 1;
  }
  return count;
}

export function classifyGesture(landmarks) {
  const fingers = countExtendedFingers(landmarks);
  const thumb = landmarks[4];
  const index = landmarks[8];
  const pinchDist = Math.hypot(thumb.x - index.x, thumb.y - index.y);

  if (pinchDist < 0.06) {
    return "closed_pinch";
  }
  if (fingers === 0) return "closed_fist";
  if (fingers >= 4) return "open_hand";
  if (fingers === 1) return "one_finger";
  if (fingers === 2) return "two_fingers";
  if (fingers === 3) return "three_fingers";
  return "open_hand";
}

function drawLandmarks(ctx, landmarks, width, height) {
  ctx.strokeStyle = "#6c8cff";
  ctx.lineWidth = 3;
  ctx.fillStyle = "#39ff14";

  const connections = [
    [0, 1], [1, 2], [2, 3], [3, 4],
    [0, 5], [5, 6], [6, 7], [7, 8],
    [0, 9], [9, 10], [10, 11], [11, 12],
    [0, 13], [13, 14], [14, 15], [15, 16],
    [0, 17], [17, 18], [18, 19], [19, 20],
    [5, 9], [9, 13], [13, 17],
  ];

  for (const [a, b] of connections) {
    ctx.beginPath();
    ctx.moveTo(landmarks[a].x * width, landmarks[a].y * height);
    ctx.lineTo(landmarks[b].x * width, landmarks[b].y * height);
    ctx.stroke();
  }

  for (const lm of landmarks) {
    ctx.beginPath();
    ctx.arc(lm.x * width, lm.y * height, 5, 0, Math.PI * 2);
    ctx.fill();
  }
}

async function initHandLandmarker() {
  const { HandLandmarker, FilesetResolver } = await import(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/+esm"
  );

  const vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/wasm"
  );

  return HandLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numHands: 1,
  });
}

export function isWebcamRunning() {
  return running;
}

export async function startWebcamGestures({ videoEl, canvasEl, overlayEl, onGesture, onStatus }) {
  if (running) return true;

  try {
    handLandmarker = await initHandLandmarker();
  } catch (e) {
    onStatus?.("MediaPipe failed to load: " + e.message);
    return false;
  }

  try {
    videoStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 } },
      audio: false,
    });
  } catch (e) {
    onStatus?.("Camera denied: " + e.message);
    return false;
  }

  videoEl.srcObject = videoStream;
  await videoEl.play();

  const ctx = canvasEl.getContext("2d");
  running = true;
  lastGesture = null;
  stableCount = 0;
  let lastVideoTime = -1;

  function loop() {
    if (!running) return;
    animFrameId = requestAnimationFrame(loop);

    if (videoEl.readyState < 2) return;

    const w = videoEl.videoWidth;
    const h = videoEl.videoHeight;
    canvasEl.width = w;
    canvasEl.height = h;

    ctx.save();
    ctx.clearRect(0, 0, w, h);
    ctx.drawImage(videoEl, 0, 0, w, h);

    if (videoEl.currentTime !== lastVideoTime) {
      lastVideoTime = videoEl.currentTime;
      const result = handLandmarker.detectForVideo(videoEl, performance.now());

      if (result.landmarks?.length) {
        const landmarks = result.landmarks[0];
        drawLandmarks(ctx, landmarks, w, h);

        const gesture = classifyGesture(landmarks);
        overlayEl.textContent = GESTURE_LABELS[gesture] || gesture;

        if (gesture === lastGesture) {
          stableCount += 1;
        } else {
          stableCount = 0;
          lastGesture = gesture;
        }

        const now = Date.now();
        if (stableCount >= 8 && now - lastTriggerTime > 2500) {
          lastTriggerTime = now;
          stableCount = 0;
          onGesture?.(gesture);
        }
      } else {
        overlayEl.textContent = "Show your hand to the camera";
      }
    }
    ctx.restore();
  }

  loop();
  onStatus?.("Webcam + MediaPipe active");
  return true;
}

export function stopWebcamGestures({ videoEl, overlayEl }) {
  running = false;
  if (animFrameId) cancelAnimationFrame(animFrameId);
  if (videoStream) {
    videoStream.getTracks().forEach((t) => t.stop());
    videoStream = null;
  }
  if (videoEl) videoEl.srcObject = null;
  overlayEl && (overlayEl.textContent = "Camera stopped");
}
