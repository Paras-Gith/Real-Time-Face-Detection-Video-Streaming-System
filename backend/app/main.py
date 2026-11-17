import base64
import io
import time
import uuid

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image, UnidentifiedImageError

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


def _decode_image(raw: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Could not decode image.") from exc


def _encode_jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


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
        image = _decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    annotated_image, roi = detect_face_and_draw(image)
    await storage.save_roi(session=session, frame_id=frame_id, timestamp=timestamp, roi=roi)

    return StreamingResponse(
        io.BytesIO(_encode_jpeg(annotated_image)),
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


@app.websocket("/ws/stream")
async def stream_frames(
    websocket: WebSocket,
    session: AsyncSession = Depends(get_session),
):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_bytes()
            try:
                image = _decode_image(raw)
            except ValueError as exc:
                await websocket.send_json({"error": str(exc)})
                continue

            frame_id = str(uuid.uuid4())
            timestamp = time.time()
            annotated_image, roi = detect_face_and_draw(image)
            await storage.save_roi(
                session=session,
                frame_id=frame_id,
                timestamp=timestamp,
                roi=roi,
            )

            await websocket.send_json({
                "frame_id": frame_id,
                "timestamp": timestamp,
                "face_detected": roi is not None,
                "roi": roi,
                "annotated_frame": base64.b64encode(
                    _encode_jpeg(annotated_image)
                ).decode("ascii"),
            })
    except WebSocketDisconnect:
        return


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