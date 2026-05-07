import io
import time
import uuid
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import Depends
from app.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image

from app.detector import detect_face_and_draw
from app.storage import save_roi, get_all_rois, get_roi_by_frame

app = FastAPI(
    title="Face Detection API",
    description="Accepts video frames, detects faces, stores ROI, returns annotated frames.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Endpoint 1: Receive a video frame ───────────────────────────────────────
@app.post("/feed/upload")
async def upload_frame(file: UploadFile = File(...),
                       session: AsyncSession = Depends(get_session)):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only JPEG/PNG frames supported.")

    raw = await file.read()
    frame_id = str(uuid.uuid4())
    timestamp = time.time()

    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode image.")

    annotated_image, roi = detect_face_and_draw(image)

    # Store in DB (in-memory for P1, PostgreSQL in P2)
    record = save_roi(session=session ,frame_id=frame_id, timestamp=timestamp, roi=roi)

    # Return annotated frame as JPEG + ROI metadata in headers
    buf = io.BytesIO()
    annotated_image.save(buf, format="JPEG")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/jpeg",
        headers={
            "X-Frame-ID": frame_id,
            "X-ROI": str(roi) if roi else "null",
            "X-Face-Detected": "true" if roi else "false",
        },
    )


# ─── Endpoint 2: Serve processed frame by frame_id ───────────────────────────
@app.get("/feed/frame/{frame_id}", summary="Retrieve a processed frame by ID")
async def get_frame(frame_id: str,
                    session: AsyncSession = Depends(get_session)):
    """
    Returns the ROI data for a previously processed frame.
    In P2 this will stream the actual annotated image from storage.
    """
    record = await get_roi_by_frame(session=session, frame_id=frame_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Frame '{frame_id}' not found.")
    return JSONResponse(content=record)


# ─── Endpoint 3: Serve ROI data ───────────────────────────────────────────────
@app.get("/roi", summary="Get all stored ROI records")
async def get_roi_data(limit: int = 50, offset: int = 0, session: AsyncSession = Depends(get_session)):
    """
    Returns all stored ROI records from the database.
    Each record contains frame_id, timestamp, and bounding box coordinates.
    """
    records = await get_all_rois(session=session, limit=limit, offset=offset)
    return JSONResponse(content={
        "count": len(records),
        "limit": limit,
        "offset": offset,
        "results": records,
    })


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}