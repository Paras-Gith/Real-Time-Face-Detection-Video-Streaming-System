# Real-Time Face Detection Video Streaming System

A containerised full-stack application that accepts a live webcam feed, detects faces in real time using MediaPipe, draws an axis-aligned bounding box (ROI) using Pillow (no OpenCV), stores detection data in PostgreSQL, and streams annotated frames back to a React frontend over WebSocket.

---

## Table of Contents

- [What It Does](#what-it-does)
- [How It Works](#how-it-works)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [How to Run](#how-to-run)
  - [Option 1 — Docker Compose (recommended)](#option-1--docker-compose-recommended)
  - [Option 2 — Without Docker](#option-2--without-docker)
- [API Endpoints](#api-endpoints)
- [WebSocket Protocol](#websocket-protocol)
- [Database Schema](#database-schema)
- [How to Use the Frontend](#how-to-use-the-frontend)
- [Running Tests](#running-tests)
- [Architecture](#architecture)
- [AI Collaboration](#ai-collaboration)

---

## What It Does

1. Opens your webcam in the browser
2. Sends video frames to the backend over WebSocket at ~10 fps
3. Backend detects a face in each frame using MediaPipe
4. Draws a green bounding box around the face using Pillow (PIL) — no OpenCV
5. Saves the bounding box coordinates (ROI) to PostgreSQL
6. Returns the annotated frame as base64 JPEG back to the browser
7. Browser renders the annotated frame on a canvas in real time
8. ROI history is displayed in a side panel, pulled from the database via REST

---

## How It Works

```
Browser (React + WebSocket)
        │
        │  sends: raw JPEG bytes (each frame)
        ▼
FastAPI Backend (port 8000)
        │
        ├── MediaPipe FaceDetector  →  finds face coordinates
        ├── Pillow ImageDraw        →  draws green rectangle on frame
        ├── PostgreSQL (asyncpg)    →  stores ROI record
        │
        │  returns: JSON { frame_id, roi, annotated_frame (base64) }
        ▼
Browser renders annotated frame on <canvas>
        │
        └── Every 3s: GET /roi  →  fetch detection history from DB
```

### Face Detection Pipeline

```
1. Receive JPEG bytes via WebSocket
2. Decode to PIL Image
3. Convert to numpy RGB array
4. Run MediaPipe FaceDetector (blaze_face_short_range.tflite)
5. Extract bounding box in absolute pixels (x, y, width, height)
6. Draw axis-aligned rectangle using PIL.ImageDraw.rectangle()
7. Add confidence label using PIL.ImageDraw.text()
8. Save ROI to PostgreSQL
9. Encode annotated image as base64 JPEG
10. Send JSON response back to client
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, WebSocket API, Canvas API |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Face Detection | MediaPipe 0.10.x (Tasks API) |
| ROI Drawing | Pillow (PIL) — no OpenCV |
| Database | PostgreSQL 16, SQLAlchemy async, asyncpg |
| Containers | Docker, Docker Compose |
| Testing | pytest, pytest-asyncio, httpx |

---

## Requirements

### To run with Docker (recommended)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux)
- Git

### To run without Docker
- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- pip packages: see `backend/requirements.txt`
- npm packages: see `frontend/package.json`

---

## Project Structure

```
Real-Time-Face-Detection-Video-Streaming-System/
│
├── docker-compose.yml          ← wires all 3 services together
├── pytest.ini                  ← test configuration
├── architecture.png            ← system architecture diagram
├── README.md                   ← this file
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             ← FastAPI app, 3 REST endpoints + WebSocket
│       ├── detector.py         ← MediaPipe face detection + Pillow ROI drawing
│       ├── database.py         ← SQLAlchemy async engine + ROIRecord model
│       └── storage.py          ← DB CRUD: save_roi, get_roi_by_frame, get_all_rois
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx            ← React entry point
│       ├── App.jsx             ← WebSocket client, canvas renderer, ROI panel
│       └── App.css             ← dark industrial theme
│
├── tests/
│   ├── conftest.py             ← shared fixtures, in-memory storage patch
│   ├── test_endpoints.py       ← REST endpoint tests (13 tests)
│   ├── test_detector.py        ← face detection unit tests (10 tests)
│   └── test_storage.py         ← storage layer tests (9 tests)
│
└── .devcontainer/
    └── devcontainer.json       ← Codespace port forwarding config
```

---

## How to Run

### Option 1 — Docker Compose (recommended)

Works on Windows, Mac, and Linux. Starts all 3 services (PostgreSQL, backend, frontend) with one command.

**Step 1 — Clone the repository**
```bash
git clone <your-repo-url>
cd Real-Time-Face-Detection-Video-Streaming-System
```

**Step 2 — Start everything**
```bash
docker-compose up --build
```

**Step 3 — Open the app**

Navigate to: **http://localhost:5173**

On first startup, the MediaPipe face detection model (~400KB) downloads automatically and is cached in a Docker volume for future runs.

**To stop:**
```bash
docker-compose down
```

**To stop and clear all data:**
```bash
docker-compose down --volumes
```

---

### Option 2 — Without Docker

**Step 1 — Start PostgreSQL**

Using Docker for just the database:
```bash
docker run -d --name facedb \
  -e POSTGRES_DB=facedb \
  -e POSTGRES_USER=faceuser \
  -e POSTGRES_PASSWORD=facepass \
  -p 5432:5432 \
  postgres:16-alpine
```

Or use your own PostgreSQL installation and create a database called `facedb`.

**Step 2 — Start the backend**

Windows:
```cmd
cd backend
pip install -r requirements.txt
set DATABASE_URL=postgresql+asyncpg://faceuser:facepass@localhost:5432/facedb
uvicorn app.main:app --reload --port 8000
```

Mac/Linux:
```bash
cd backend
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://faceuser:facepass@localhost:5432/facedb \
  uvicorn app.main:app --reload --port 8000
```

**Step 3 — Start the frontend**
```bash
cd frontend
npm install
npm run dev
```

**Step 4 — Open the app**

Navigate to: **http://localhost:5173**

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/feed/upload` | Upload a JPEG/PNG frame. Returns annotated JPEG with ROI headers. |
| `GET` | `/feed/frame/{frame_id}` | Get ROI metadata for a specific frame by ID. |
| `GET` | `/roi?limit=50&offset=0` | Get all ROI records from PostgreSQL (paginated). |
| `WS` | `/ws/stream` | Real-time bidirectional WebSocket video stream. |
| `GET` | `/health` | Health check — returns `{ "status": "ok" }`. |
| `GET` | `/docs` | Swagger UI — interactive API documentation. |

### POST /feed/upload — Response Headers

| Header | Example | Description |
|--------|---------|-------------|
| `X-Frame-ID` | `550e8400-e29b-41d4-a716-446655440000` | UUID assigned to this frame |
| `X-Face-Detected` | `true` | Whether a face was found |
| `X-ROI-X` | `120` | Bounding box left edge (px) |
| `X-ROI-Y` | `80` | Bounding box top edge (px) |
| `X-ROI-W` | `200` | Bounding box width (px) |
| `X-ROI-H` | `220` | Bounding box height (px) |

---

## WebSocket Protocol

**Endpoint:** `ws://localhost:8000/ws/stream`

**Client → Server:** Raw JPEG bytes of each video frame

**Server → Client:** JSON object per frame

```json
{
  "frame_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1714567890.123,
  "face_detected": true,
  "roi": {
    "x": 120,
    "y": 80,
    "width": 200,
    "height": 220,
    "confidence": 0.97
  },
  "annotated_frame": "<base64-encoded JPEG with green bounding box>"
}
```

When no face is detected:
```json
{
  "frame_id": "...",
  "timestamp": 1714567890.456,
  "face_detected": false,
  "roi": null,
  "annotated_frame": "<base64-encoded original JPEG>"
}
```

---

## Database Schema

**Table: `roi_records`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | `INTEGER` PK | Auto-increment primary key |
| `frame_id` | `VARCHAR(36)` UNIQUE | UUID assigned to each frame |
| `timestamp` | `FLOAT` INDEX | Unix epoch timestamp |
| `face_detected` | `BOOLEAN` | Whether a face was found |
| `x` | `INTEGER` | Bounding box left edge (null if no face) |
| `y` | `INTEGER` | Bounding box top edge (null if no face) |
| `width` | `INTEGER` | Bounding box width (null if no face) |
| `height` | `INTEGER` | Bounding box height (null if no face) |
| `confidence` | `FLOAT` | Detection confidence 0–1 (null if no face) |

---

## How to Use the Frontend

1. Open **http://localhost:5173** in your browser
2. Allow camera permissions when prompted
3. Click **▶ Start Stream**
4. Your webcam feed appears on the canvas
5. When a face is detected, a **green bounding box** appears around it
6. The **Current ROI** panel shows live coordinates and confidence score
7. The **Recent Detections** panel shows the last 8 detections from the database
8. Click **■ Stop** to end the stream

---

## Running Tests

Tests run without a real database — storage is patched to in-memory automatically.

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all 32 tests
pytest

# Run a specific test file
pytest tests/test_endpoints.py
pytest tests/test_detector.py
pytest tests/test_storage.py
```

**Test coverage:**

| File | Tests | What it covers |
|------|-------|----------------|
| `test_endpoints.py` | 13 | All 3 REST endpoints, status codes, headers, pagination |
| `test_detector.py` | 10 | Face detection pipeline, ROI keys, no-OpenCV compliance |
| `test_storage.py` | 9 | save/get/list/pagination on storage layer |

---

## Architecture

See `architecture.png` for the full system diagram showing all containers, data flow, database schema, and Docker volumes.

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Compose Network                  │
│                                                          │
│  ┌─────────────┐    WebSocket     ┌──────────────────┐  │
│  │   Browser   │ ◄──────────────► │  FastAPI Backend │  │
│  │  React +    │    REST /roi     │  :8000           │  │
│  │  Canvas     │ ─────────────►   │                  │  │
│  │  :5173      │                  │  MediaPipe       │  │
│  └─────────────┘                  │  Pillow (no CV2) │  │
│                                   │  SQLAlchemy      │  │
│                                   └────────┬─────────┘  │
│                                            │ asyncpg    │
│                                   ┌────────▼─────────┐  │
│                                   │   PostgreSQL 16  │  │
│                                   │   :5432          │  │
│                                   │   roi_records    │  │
│                                   └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Docker volumes:**
- `pgdata` — PostgreSQL data, persists between container restarts
- `model_cache` — MediaPipe `.tflite` model, avoids re-downloading on restart

---

## AI Collaboration

This project was built with AI assistance (Claude by Anthropic). AI was used for:
- Debugging Docker networking issues in GitHub Codespaces
- Generating the architecture diagram PNG
- Troubleshooting MediaPipe Tasks API compatibility (v0.10.x)

All generated code was reviewed, corrected, and tested manually.
