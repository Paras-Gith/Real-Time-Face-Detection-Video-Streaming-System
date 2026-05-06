"""
Unit tests for the face detection pipeline (detector.py).

Tests:
- detect_face_and_draw always returns a PIL Image
- ROI dict has the correct keys when a face is detected
- ROI coordinates are within image bounds
- Pillow (not OpenCV) is used for drawing
- No-face frames return (image, None)
"""

import io
import numpy as np
import pytest
from PIL import Image

from app.detector import detect_face_and_draw


def solid_image(w=320, h=240, color=(120, 100, 80)) -> Image.Image:
    return Image.fromarray(np.full((h, w, 3), color, dtype=np.uint8))


# ── Return type tests ─────────────────────────────────────────────────────────

def test_returns_pil_image():
    """detect_face_and_draw must always return a PIL Image as first value."""
    img = solid_image()
    result_img, roi = detect_face_and_draw(img)
    assert isinstance(result_img, Image.Image)


def test_returns_none_roi_for_blank_image():
    """A blank image has no face — roi should be None."""
    img = solid_image()
    _, roi = detect_face_and_draw(img)
    assert roi is None


def test_output_image_same_size_as_input():
    """Output image must be the same dimensions as the input."""
    w, h = 640, 480
    img = solid_image(w, h)
    result_img, _ = detect_face_and_draw(img)
    assert result_img.size == (w, h)


def test_output_image_is_rgb():
    """Output image must be in RGB mode."""
    img = solid_image()
    result_img, _ = detect_face_and_draw(img)
    assert result_img.mode == "RGB"


def test_original_image_not_mutated():
    """Input image should not be modified (function must work on a copy)."""
    img = solid_image(color=(42, 42, 42))
    original_pixels = list(img.getdata())
    detect_face_and_draw(img)
    assert list(img.getdata()) == original_pixels


# ── ROI structure tests ───────────────────────────────────────────────────────

def test_roi_has_required_keys_when_face_found(monkeypatch):
    """When a face is detected, roi dict must have x, y, width, height, confidence."""
    # Monkeypatch detector to simulate a face detection result
    import app.detector as det

    class FakeBBox:
        origin_x = 50; origin_y = 40; width = 120; height = 130

    class FakeCategory:
        score = 0.95

    class FakeDetection:
        bounding_box = FakeBBox()
        categories = [FakeCategory()]

    class FakeResult:
        detections = [FakeDetection()]

    original_detect = det._detector.detect
    det._detector.detect = lambda mp_img: FakeResult()

    img = solid_image(320, 240)
    _, roi = detect_face_and_draw(img)

    det._detector.detect = original_detect  # restore

    assert roi is not None
    for key in ("x", "y", "width", "height", "confidence"):
        assert key in roi, f"Missing key: {key}"


def test_roi_coordinates_within_bounds(monkeypatch):
    """ROI x, y, width, height must not exceed image dimensions."""
    import app.detector as det

    class FakeBBox:
        origin_x = 10; origin_y = 10; width = 200; height = 180

    class FakeCategory:
        score = 0.90

    class FakeDetection:
        bounding_box = FakeBBox()
        categories = [FakeCategory()]

    class FakeResult:
        detections = [FakeDetection()]

    original = det._detector.detect
    det._detector.detect = lambda mp_img: FakeResult()

    W, H = 320, 240
    img = solid_image(W, H)
    _, roi = detect_face_and_draw(img)

    det._detector.detect = original

    assert roi["x"] >= 0
    assert roi["y"] >= 0
    assert roi["x"] + roi["width"]  <= W
    assert roi["y"] + roi["height"] <= H


def test_roi_confidence_between_0_and_1(monkeypatch):
    """Confidence score must be in [0, 1]."""
    import app.detector as det

    class FakeBBox:
        origin_x = 20; origin_y = 20; width = 80; height = 90

    class FakeCategory:
        score = 0.87

    class FakeDetection:
        bounding_box = FakeBBox()
        categories = [FakeCategory()]

    class FakeResult:
        detections = [FakeDetection()]

    original = det._detector.detect
    det._detector.detect = lambda mp_img: FakeResult()

    _, roi = detect_face_and_draw(solid_image())

    det._detector.detect = original

    assert 0.0 <= roi["confidence"] <= 1.0


# ── No OpenCV test ─────────────────────────────────────────────────────────────

def test_opencv_not_imported():
    """
    detector.py must NOT import cv2 (OpenCV).
    This verifies compliance with the no-OpenCV requirement.
    """
    import app.detector as det
    import sys
    # Check cv2 is not in detector module's globals
    assert "cv2" not in vars(det), "cv2 (OpenCV) must not be used in detector.py"
    # Also verify cv2 was not imported as a side effect of importing detector
    # (it might exist elsewhere but not through our module)
    detector_source = open(det.__file__).read()
    assert "import cv2" not in detector_source, "detector.py must not contain 'import cv2'"
    assert "cv2." not in detector_source, "detector.py must not use cv2.*"


def test_pillow_used_for_drawing():
    """detector.py must use PIL.ImageDraw for drawing (not OpenCV)."""
    import app.detector as det
    source = open(det.__file__).read()
    assert "ImageDraw" in source, "detector.py must use PIL.ImageDraw"
    assert "draw.rectangle" in source, "ROI must be drawn with draw.rectangle()"