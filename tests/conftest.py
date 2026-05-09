"""
Shared pytest fixtures for all tests.
Uses in-memory storage — no real database needed.
"""

import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from PIL import Image
import numpy as np

# ── Module-level in-memory store ──────────────────────────────────────────────
_store = {}


# ── Fake storage functions ────────────────────────────────────────────────────
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


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def patch_storage(monkeypatch):
    import app.storage as storage_mod
    monkeypatch.setattr(storage_mod, "save_roi", fake_save_roi)
    monkeypatch.setattr(storage_mod, "get_roi_by_frame", fake_get_roi_by_frame)
    monkeypatch.setattr(storage_mod, "get_all_rois", fake_get_all_rois)
    _store.clear()
    yield _store


@pytest.fixture(autouse=True)
def patch_db():
    from app.main import app
    from app.database import get_session

    async def override_get_session():
        yield None

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── Helper functions ──────────────────────────────────────────────────────────
def make_jpeg(width=320, height=240, color=(100, 150, 200)) -> bytes:
    img = Image.fromarray(
        np.full((height, width, 3), color, dtype=np.uint8)
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_jpeg_with_face(width=640, height=480) -> bytes:
    return make_jpeg(width, height, color=(200, 180, 160))