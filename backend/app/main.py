import io
import time
import uuid
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image

from app.detector import detect_face_and_draw
from app.database import init_db, get_session
import app.storage as storage

app = FastAPI(
    title="Face Detection API",
    description="Accepts video frames, detects faces, stores ROI, returns annotated frames.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()


# ─── Endpoint 1: Receive a video frame ───────────────────────────────────────
@app.post("/feed/upload")
async def upload_frame(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
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
    await storage.save_roi(session=session, frame_id=frame_id, timestamp=timestamp, roi=roi)

    buf = io.BytesIO()
    annotated_image.save(buf, format="JPEG")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/jpeg",
        headers={
            "X-Frame-ID":      frame_id,
            "X-Face-Detected": "true" if roi else "false",
            "X-ROI-X":         str(roi["x"])      if roi else "",
            "X-ROI-Y":         str(roi["y"])      if roi else "",
            "X-ROI-W":         str(roi["width"])  if roi else "",
            "X-ROI-H":         str(roi["height"]) if roi else "",
        },
    )


# ─── Endpoint 2: Serve processed frame by frame_id ───────────────────────────
@app.get("/feed/frame/{frame_id}")
async def get_frame(
    frame_id: str,
    session: AsyncSession = Depends(get_session),
):
    record = await storage.get_roi_by_frame(session=session, frame_id=frame_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Frame '{frame_id}' not found.")
    return JSONResponse(content=record)


# ─── Endpoint 3: Serve ROI data ──────────────────────────────────────────────
@app.get("/roi")
async def get_roi_data(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    records = await storage.get_all_rois(session=session, limit=limit, offset=offset)
    return JSONResponse(content={
        "count":   len(records),
        "limit":   limit,
        "offset":  offset,
        "results": records,
    })


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}