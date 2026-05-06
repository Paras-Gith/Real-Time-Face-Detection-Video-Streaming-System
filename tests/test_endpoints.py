"""
E2E tests for the 3 REST API endpoints.

Endpoint 1: POST /feed/upload
Endpoint 2: GET  /feed/frame/{frame_id}
Endpoint 3: GET  /roi
"""

import io
import pytest
from PIL import Image

from tests.conftest import make_jpeg


# ══════════════════════════════════════════════════════════════════════════════
# POST /feed/upload
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_upload_returns_jpeg(client):
    """Uploading a valid JPEG should return an annotated JPEG image."""
    jpeg_bytes = make_jpeg()
    response = await client.post(
        "/feed/upload",
        files={"file": ("frame.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_upload_returns_frame_id_header(client):
    """Response should include X-Frame-ID header with a UUID."""
    jpeg_bytes = make_jpeg()
    response = await client.post(
        "/feed/upload",
        files={"file": ("frame.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    frame_id = response.headers.get("x-frame-id")
    assert frame_id is not None
    assert len(frame_id) == 36   # UUID4 format


@pytest.mark.asyncio
async def test_upload_face_detected_header(client):
    """X-Face-Detected header must be 'true' or 'false'."""
    jpeg_bytes = make_jpeg()
    response = await client.post(
        "/feed/upload",
        files={"file": ("frame.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.headers.get("x-face-detected") in ("true", "false")


@pytest.mark.asyncio
async def test_upload_invalid_content_type(client):
    """Uploading a non-image file should return 400."""
    response = await client.post(
        "/feed/upload",
        files={"file": ("data.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_corrupt_image(client):
    """Uploading corrupt bytes as JPEG should return 400."""
    response = await client.post(
        "/feed/upload",
        files={"file": ("bad.jpg", b"\x00\x01\x02\x03bad data", "image/jpeg")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_png_accepted(client):
    """PNG images should also be accepted."""
    img = Image.new("RGB", (100, 100), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    response = await client.post(
        "/feed/upload",
        files={"file": ("frame.png", buf.getvalue(), "image/png")},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_response_is_valid_image(client):
    """The returned bytes must decode as a valid JPEG image."""
    jpeg_bytes = make_jpeg()
    response = await client.post(
        "/feed/upload",
        files={"file": ("frame.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    returned_img = Image.open(io.BytesIO(response.content))
    assert returned_img.mode == "RGB"
    assert returned_img.size[0] > 0
    assert returned_img.size[1] > 0


# ══════════════════════════════════════════════════════════════════════════════
# GET /feed/frame/{frame_id}
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_frame_after_upload(client):
    """After uploading a frame, GET /feed/frame/{id} should return its ROI data."""
    jpeg_bytes = make_jpeg()
    upload = await client.post(
        "/feed/upload",
        files={"file": ("frame.jpg", jpeg_bytes, "image/jpeg")},
    )
    frame_id = upload.headers["x-frame-id"]

    response = await client.get(f"/feed/frame/{frame_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["frame_id"] == frame_id
    assert "face_detected" in data
    assert "roi" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_get_frame_not_found(client):
    """Requesting a nonexistent frame_id should return 404."""
    response = await client.get("/feed/frame/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# GET /roi
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_roi_endpoint_returns_list(client):
    """GET /roi should return a JSON object with a results list."""
    response = await client.get("/roi")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "count" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_roi_grows_after_uploads(client, patch_storage):
    """Each upload should add a record retrievable via /roi."""
    patch_storage.clear()

    for _ in range(3):
        await client.post(
            "/feed/upload",
            files={"file": ("frame.jpg", make_jpeg(), "image/jpeg")},
        )

    response = await client.get("/roi")
    data = response.json()
    assert data["count"] >= 3


@pytest.mark.asyncio
async def test_roi_pagination(client, patch_storage):
    """limit and offset parameters should paginate results."""
    patch_storage.clear()

    for _ in range(5):
        await client.post(
            "/feed/upload",
            files={"file": ("f.jpg", make_jpeg(), "image/jpeg")},
        )

    page1 = await client.get("/roi?limit=2&offset=0")
    page2 = await client.get("/roi?limit=2&offset=2")

    p1_data = page1.json()
    p2_data = page2.json()

    assert len(p1_data["results"]) == 2
    assert len(p2_data["results"]) == 2

    ids1 = {r["frame_id"] for r in p1_data["results"]}
    ids2 = {r["frame_id"] for r in p2_data["results"]}
    assert ids1.isdisjoint(ids2), "Pages should not overlap"


# ══════════════════════════════════════════════════════════════════════════════
# GET /health
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"