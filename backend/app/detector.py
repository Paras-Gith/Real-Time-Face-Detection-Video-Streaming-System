"""
P1 Storage — simple in-memory dict.
This module will be swapped for a PostgreSQL/SQLAlchemy implementation in P2.
The interface (save_roi, get_roi_by_frame, get_all_rois) stays the same.
"""

from typing import Optional, Dict, List

_store: Dict[str, dict] = {}   # frame_id → record


def save_roi(frame_id: str, timestamp: float, roi: Optional[dict]) -> dict:
    """
    Persist ROI data for a frame.
    Returns the saved record.
    """
    record = {
        "frame_id": frame_id,
        "timestamp": timestamp,
        "face_detected": roi is not None,
        "roi": roi,   # None if no face found
    }
    _store[frame_id] = record
    return record


def get_roi_by_frame(frame_id: str) -> Optional[dict]:
    """Return the record for a given frame_id, or None."""
    return _store.get(frame_id)


def get_all_rois(limit: int = 50, offset: int = 0) -> List[dict]:
    """Return all stored records, newest first, with pagination."""
    all_records = list(_store.values())
    all_records.sort(key=lambda r: r["timestamp"], reverse=True)
    return all_records[offset: offset + limit]


def clear_store():
    """Utility for tests."""
    _store.clear()