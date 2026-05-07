"""
PostgreSQL storage — replaces P1 in-memory dict.
Same interface: save_roi, get_roi_by_frame, get_all_rois.
"""

from typing import Optional, Dict, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import ROIRecord


def _to_dict(record: ROIRecord) -> dict:
    has_face = record.face_detected is True
    return {
        "frame_id":     record.frame_id,
        "timestamp":    record.timestamp,
        "face_detected": record.face_detected,
        "roi": {
            "x":          record.x,
            "y":          record.y,
            "width":      record.width,
            "height":     record.height,
            "confidence": record.confidence,
        } if has_face else None,
    }


async def save_roi(
    session: AsyncSession,
    frame_id: str,
    timestamp: float,
    roi: Optional[Dict],
) -> dict:
    record = ROIRecord(
        frame_id      = frame_id,
        timestamp     = timestamp,
        face_detected = roi is not None,
        x             = roi["x"]          if roi else None,
        y             = roi["y"]          if roi else None,
        width         = roi["width"]      if roi else None,
        height        = roi["height"]     if roi else None,
        confidence    = roi["confidence"] if roi else None,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return _to_dict(record)


async def get_roi_by_frame(
    session: AsyncSession,
    frame_id: str,
) -> Optional[dict]:
    result = await session.execute(
        select(ROIRecord).where(ROIRecord.frame_id == frame_id)
    )
    record = result.scalar_one_or_none()
    return _to_dict(record) if record else None


async def get_all_rois(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> List[dict]:
    result = await session.execute(
        select(ROIRecord)
        .order_by(desc(ROIRecord.timestamp))
        .limit(limit)
        .offset(offset)
    )
    return [_to_dict(r) for r in result.scalars().all()]