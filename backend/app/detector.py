"""
Face detection using MediaPipe Tasks API (v0.10.x).
ROI bounding box drawn with Pillow (PIL) — NO OpenCV used anywhere.

MediaPipe 0.10.x requires a .tflite model file.
The model is auto-downloaded on first run and cached in the models/ folder.
"""

import os
import urllib.request
from typing import Optional, Tuple, Dict
from PIL import Image, ImageDraw
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# ── Model setup ──────────────────────────────────────────────────────────────
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "blaze_face_short_range.tflite")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)


def _ensure_model() -> str:
    """Download the MediaPipe face detection model if not already cached."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        print(f"[detector] Downloading MediaPipe model to {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[detector] Model downloaded successfully.")
    return MODEL_PATH


# Initialise detector once at module load
_model_path = _ensure_model()

_base_options = mp_python.BaseOptions(model_asset_path=_model_path)
_detector_options = mp_vision.FaceDetectorOptions(
    base_options=_base_options,
    min_detection_confidence=0.5,
)
_detector = mp_vision.FaceDetector.create_from_options(_detector_options)


# ── Main function ─────────────────────────────────────────────────────────────
def detect_face_and_draw(
    image: Image.Image,
) -> Tuple[Image.Image, Optional[Dict]]:
    """
    Given a PIL Image:
      1. Run MediaPipe face detection (Tasks API).
      2. If a face is found, compute the axis-aligned minimal bounding box (ROI).
      3. Draw the rectangle using Pillow — no OpenCV.
      4. Return (annotated_image, roi_dict) or (original_image, None) if no face.

    roi_dict keys: x, y, width, height (all in absolute pixels, top-left origin)
    """
    width, height = image.size
    rgb_array = np.array(image.convert("RGB"), dtype=np.uint8)

    # Wrap in MediaPipe Image
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_array)

    # Run detection
    result = _detector.detect(mp_image)

    if not result.detections:
        return image.copy(), None

    # Problem states only ONE face — take highest confidence detection
    detection = result.detections[0]
    bbox = detection.bounding_box

    # bbox already in absolute pixels for Tasks API
    x = max(0, bbox.origin_x)
    y = max(0, bbox.origin_y)
    w = min(bbox.width, width - x)
    h = min(bbox.height, height - y)

    confidence = detection.categories[0].score if detection.categories else 0.0

    roi = {
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "confidence": round(confidence, 4),
    }

    # ── Draw axis-aligned bounding box using Pillow (PIL.ImageDraw) ──────────
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)

    # Bounding box rectangle
    draw.rectangle([x, y, x + w, y + h], outline="#00FF41", width=3)

    # Label background + text
    label = f"face {confidence:.0%}"
    text_x = x + 4
    text_y = max(0, y - 20)
    label_w = len(label) * 7 + 6
    draw.rectangle([text_x - 2, text_y, text_x + label_w, text_y + 17], fill="#00FF41")
    draw.text((text_x, text_y + 1), label, fill="#000000")

    return annotated, roi