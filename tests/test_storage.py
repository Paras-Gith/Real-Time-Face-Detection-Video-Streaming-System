"""
Unit tests for the storage layer (storage.py).
Uses the in-memory patch from conftest so no real DB needed.
"""

import time
import pytest


# ── save_roi ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_roi_with_face(patch_storage):
    from app.storage import save_roi
    patch_storage.clear()

    roi = {"x": 10, "y": 20, "width": 80, "height": 90, "confidence": 0.95}
    record = await save_roi(
        session=None,
        frame_id="test-frame-001",
        timestamp=time.time(),
        roi=roi,
    )

    assert record["frame_id"]     == "test-frame-001"
    assert record["face_detected"] is True
    assert record["roi"]["x"]     == 10
    assert record["roi"]["confidence"] == 0.95


@pytest.mark.asyncio
async def test_save_roi_without_face(patch_storage):
    from app.storage import save_roi
    patch_storage.clear()

    record = await save_roi(
        session=None,
        frame_id="test-frame-002",
        timestamp=time.time(),
        roi=None,
    )

    assert record["face_detected"] is False
    assert record["roi"] is None


@pytest.mark.asyncio
async def test_save_roi_stores_in_db(patch_storage):
    from app.storage import save_roi
    patch_storage.clear()

    await save_roi(session=None, frame_id="frame-abc", timestamp=1.0, roi=None)
    assert "frame-abc" in patch_storage


# ── get_roi_by_frame ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_roi_by_frame_found(patch_storage):
    from app.storage import save_roi, get_roi_by_frame
    patch_storage.clear()

    await save_roi(session=None, frame_id="frame-xyz", timestamp=2.0, roi=None)
    result = await get_roi_by_frame(session=None, frame_id="frame-xyz")

    assert result is not None
    assert result["frame_id"] == "frame-xyz"


@pytest.mark.asyncio
async def test_get_roi_by_frame_not_found(patch_storage):
    from app.storage import get_roi_by_frame
    patch_storage.clear()

    result = await get_roi_by_frame(session=None, frame_id="does-not-exist")
    assert result is None


# ── get_all_rois ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_rois_empty(patch_storage):
    from app.storage import get_all_rois
    patch_storage.clear()

    results = await get_all_rois(session=None)
    assert results == []


@pytest.mark.asyncio
async def test_get_all_rois_returns_all(patch_storage):
    from app.storage import save_roi, get_all_rois
    patch_storage.clear()

    for i in range(4):
        await save_roi(session=None, frame_id=f"frame-{i}", timestamp=float(i), roi=None)

    results = await get_all_rois(session=None)
    assert len(results) == 4


@pytest.mark.asyncio
async def test_get_all_rois_ordered_newest_first(patch_storage):
    from app.storage import save_roi, get_all_rois
    patch_storage.clear()

    await save_roi(session=None, frame_id="old", timestamp=1000.0, roi=None)
    await save_roi(session=None, frame_id="new", timestamp=9000.0, roi=None)

    results = await get_all_rois(session=None)
    assert results[0]["frame_id"] == "new"
    assert results[1]["frame_id"] == "old"


@pytest.mark.asyncio
async def test_get_all_rois_pagination(patch_storage):
    from app.storage import save_roi, get_all_rois
    patch_storage.clear()

    for i in range(6):
        await save_roi(session=None, frame_id=f"pg-frame-{i}", timestamp=float(i), roi=None)

    page1 = await get_all_rois(session=None, limit=3, offset=0)
    page2 = await get_all_rois(session=None, limit=3, offset=3)

    assert len(page1) == 3
    assert len(page2) == 3

    ids1 = {r["frame_id"] for r in page1}
    ids2 = {r["frame_id"] for r in page2}
    assert ids1.isdisjoint(ids2)