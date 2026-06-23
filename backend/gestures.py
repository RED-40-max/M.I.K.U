"""Hand gesture detection using MediaPipe Hands."""

import threading
from typing import Callable, Optional

_detector_thread: Optional[threading.Thread] = None
_running = False
_current_gesture: Optional[str] = None
_on_gesture: Optional[Callable[[str], None]] = None

# Finger tip and pip landmark indices for MediaPipe Hands
_TIP_IDS = [4, 8, 12, 16, 20]
_PIP_IDS = [3, 6, 10, 14, 18]


def get_current_gesture() -> Optional[str]:
  return _current_gesture


def is_running() -> bool:
  return _running


def _count_extended_fingers(landmarks) -> int:
  """Count extended fingers (excluding thumb logic simplified)."""
  count = 0
  # Thumb: compare x for right hand assumption
  if landmarks[4].x < landmarks[3].x:
    count += 1
  for tip, pip in zip(_TIP_IDS[1:], _PIP_IDS[1:]):
    if landmarks[tip].y < landmarks[pip].y:
      count += 1
  return count


def _classify_gesture(landmarks) -> str:
  """Map hand landmarks to MIKU gesture names."""
  fingers = _count_extended_fingers(landmarks)

  thumb_tip = landmarks[4]
  index_tip = landmarks[8]
  pinch_dist = ((thumb_tip.x - index_tip.x) ** 2 + (thumb_tip.y - index_tip.y) ** 2) ** 0.5

  if pinch_dist < 0.05:
    # Distinguish closed vs open pinch by other fingers
    others_extended = sum(
      1
      for tip, pip in zip(_TIP_IDS[2:], _PIP_IDS[2:])
      if landmarks[tip].y < landmarks[pip].y
    )
    return "open_pinch" if others_extended >= 2 else "closed_pinch"

  if fingers == 0:
    return "closed_pinch"
  if fingers >= 4:
    return "open_hand"
  if fingers == 1:
    return "one_finger"
  if fingers == 2:
    return "two_fingers"
  if fingers == 3:
    return "three_fingers"

  return "open_hand"


def _detection_loop(camera_index: int = 0) -> None:
  """Main MediaPipe detection loop (runs in background thread)."""
  global _current_gesture, _running

  try:
    import cv2
    import mediapipe as mp
  except ImportError:
    _running = False
    return

  mp_hands = mp.solutions.hands
  hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6,
  )

  cap = cv2.VideoCapture(camera_index)
  if not cap.isOpened():
    _running = False
    return

  last_gesture = None
  stable_count = 0

  while _running:
    ok, frame = cap.read()
    if not ok:
      break

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    gesture = None
    if results.multi_hand_landmarks:
      gesture = _classify_gesture(results.multi_hand_landmarks[0].landmark)

    if gesture == last_gesture:
      stable_count += 1
    else:
      stable_count = 0
      last_gesture = gesture

    # Require 5 stable frames before triggering
    if gesture and stable_count == 5:
      _current_gesture = gesture
      if _on_gesture:
        _on_gesture(gesture)

  cap.release()
  hands.close()
  _running = False


def start_detection(
  on_gesture: Optional[Callable[[str], None]] = None,
  camera_index: int = 0,
) -> bool:
  """Start gesture detection in a background thread."""
  global _detector_thread, _running, _on_gesture

  if _running:
    return True

  _on_gesture = on_gesture
  _running = True
  _detector_thread = threading.Thread(
    target=_detection_loop,
    args=(camera_index,),
    daemon=True,
  )
  _detector_thread.start()
  return True


def stop_detection() -> None:
  """Stop gesture detection."""
  global _running
  _running = False
