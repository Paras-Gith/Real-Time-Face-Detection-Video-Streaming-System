"""
Face detection using MediaPipe.
ROI bounding box drawn with Pillow (PIL) — NO OpenCV used anywhere.
"""
from typing import Optional, Tuple, Dict
from PIL import Image, ImageDraw
import mediapipe as mp

# Initialise MediaPipe face detection once at module load
_mp_face = mp.solutions.face_detection
_detector = _mp_face.FaceDetection(
    model_selection=0,       # 0 = short-range (< 2m), 1 = full-range
    min_detection_confidence=0.5,
)


def detect_face_and_draw(
    image: Image.Image,
) -> Tuple[Image.Image, Optional[Dict]]:
    """
    Given a PIL Image:
      1. Run MediaPipe face detection.
      2. If a face is found, compute the axis-aligned minimal bounding box (ROI).
      3. Draw the rectangle on the image using Pillow — no OpenCV.
      4. Return (annotated_image, roi_dict) or (original_image, None) if no face.

    roi_dict keys: x, y, width, height (all in pixels, top-left origin)
    """
    import numpy as np

    width, height = image.size
    rgb_array = np.array(image)           # MediaPipe expects numpy RGB array

    results = _detector.process(rgb_array)

    if not results.detections:
        return image.copy(), None

    # Problem says assume only ONE face — take the first (highest confidence) detection
    detection = results.detections[0]
    bbox = detection.location_data.relative_bounding_box

    # Convert relative coords → absolute pixel coords
    x = int(bbox.xmin * width)
    y = int(bbox.ymin * height)
    w = int(bbox.width * width)
    h = int(bbox.height * height)

    # Clamp to image bounds
    x = max(0, x)
    y = max(0, y)
    w = min(w, width - x)
    h = min(h, height - y)

    roi = {"x": x, "y": y, "width": w, "height": h}

    # ── Draw axis-aligned bounding box using Pillow (PIL.ImageDraw) ──
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)

    box_coords = [x, y, x + w, y + h]
    draw.rectangle(box_coords, outline="#00FF41", width=3)

    # Small label
    label = f"face  {detection.score[0]:.0%}"
    text_x = x + 4
    text_y = max(0, y - 18)
    draw.rectangle([text_x - 2, text_y, text_x + len(label) * 7, text_y + 16], fill="#00FF41")
    draw.text((text_x, text_y), label, fill="#000000")

    return annotated, roi