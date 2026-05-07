"""
Shared pytest fixtures for P3 E2E tests.
Uses httpx.AsyncClient to test FastAPI without a running server.
Storage is patched to use in-memory for unit tests.
"""

import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from PIL import Image
import numpy as np


# ── Patch storage to in-memory before importing app ──────────────────────────
@pytest.fixture
def patch_storage():
    """
    Replace PostgreSQL storage with a simple in-memory dict for all tests.
    This means tests run without a real database.
    """
    import app.storage as storage_mod

    _store = {}

    async def fake_save_roi(session, frame_id, timestamp, roi):
        record = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "face_detected": roi is not None,
            "roi": roi,
        }
        _store[frame_id] = record
        return record

    async def fake_get_roi_by_frame(session, frame_id):
        return _store.get(frame_id)

    async def fake_get_all_rois(session, limit=50, offset=0):
        records = sorted(_store.values(), key=lambda r: r["timestamp"], reverse=True)
        return records[offset: offset + limit]

    storage_mod.save_roi         = fake_save_roi
    storage_mod.get_roi_by_frame = fake_get_roi_by_frame
    storage_mod.get_all_rois     = fake_get_all_rois

    yield _store
    _store.clear()


# ── Patch DB init to no-op ────────────────────────────────────────────────────
@pytest.fixture(autouse=True, scope="session")
def patch_db():
    import app.database as db_mod
    async def fake_init_db(): pass
    db_mod.init_db = fake_init_db

    async def fake_get_session():
        yield None   # session=None is fine since storage is patched

    db_mod.get_session = fake_get_session
    yield


# ── FastAPI test client ───────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── Helper: create a synthetic JPEG image ────────────────────────────────────
def make_jpeg(width=320, height=240, color=(100, 150, 200)) -> bytes:
    """Return raw JPEG bytes of a solid-color image."""
    img = Image.fromarray(
        np.full((height, width, 3), color, dtype=np.uint8)
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_jpeg_with_face(width=640, height=480) -> bytes:
    """
    A plain image (no real face) — used to test the pipeline flow.
    Face detection will return roi=None for synthetic images, which is correct.
    """
    return make_jpeg(width, height, color=(200, 180, 160))