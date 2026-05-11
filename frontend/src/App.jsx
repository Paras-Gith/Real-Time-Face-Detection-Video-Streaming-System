import { useState, useEffect, useRef, useCallback } from "react";
import "./App.css";


const WS_URL = `wss://${window.location.host}/ws/stream`;
const API_URL = "";


export default function App() {
  const videoRef     = useRef(null);
  const canvasRef    = useRef(null);
  const wsRef        = useRef(null);
  const streamRef    = useRef(null);
  const intervalRef  = useRef(null);

  const [status, setStatus]       = useState("idle");
  const [roi, setRoi]             = useState(null);
  const [faceDetected, setFaceDetected] = useState(false);
  const [fps, setFps]             = useState(0);
  const [roiHistory, setRoiHistory] = useState([]);
  const [error, setError]         = useState("");

  const fpsCountRef = useRef(0);
  const fpsTimerRef = useRef(null);

  useEffect(() => {
    fpsTimerRef.current = setInterval(() => {
      setFps(fpsCountRef.current);
      fpsCountRef.current = 0;
    }, 1000);
    return () => clearInterval(fpsTimerRef.current);
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/roi?limit=10`);
      const data = await res.json();
      setRoiHistory(data.results || []);
    } catch (e) {}
  }, []);

  useEffect(() => {
    const t = setInterval(fetchHistory, 3000);
    return () => clearInterval(t);
  }, [fetchHistory]);

  const startStream = useCallback(async () => {
    setError("");
    setStatus("connecting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (e) {
      setError("Camera access denied. Please allow camera permissions.");
      setStatus("idle");
      return;
    }

    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("streaming");
      intervalRef.current = setInterval(() => captureAndSend(ws), 100);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error) return;
        fpsCountRef.current += 1;
        setFaceDetected(data.face_detected);
        setRoi(data.roi);
        if (data.annotated_frame && canvasRef.current) {
          const img = new Image();
          img.onload = () => {
            const ctx = canvasRef.current?.getContext("2d");
            if (ctx) {
              canvasRef.current.width  = img.width;
              canvasRef.current.height = img.height;
              ctx.drawImage(img, 0, 0);
            }
          };
          img.src = `data:image/jpeg;base64,${data.annotated_frame}`;
        }
      } catch (e) {}
    };

    ws.onerror = () => {
      setError("WebSocket error. Is the backend running?");
      stopStream();
    };

    ws.onclose = () => {
      if (status === "streaming") setStatus("stopped");
    };
  }, []);

  const captureAndSend = (ws) => {
    if (!videoRef.current || !canvasRef.current) return;
    if (ws.readyState !== WebSocket.OPEN) return;
    const video = videoRef.current;
    const tmpCanvas = document.createElement("canvas");
    tmpCanvas.width  = video.videoWidth  || 640;
    tmpCanvas.height = video.videoHeight || 480;
    const ctx = tmpCanvas.getContext("2d");
    ctx.drawImage(video, 0, 0);
    tmpCanvas.toBlob((blob) => {
      if (blob && ws.readyState === WebSocket.OPEN) {
        blob.arrayBuffer().then((buf) => ws.send(buf));
      }
    }, "image/jpeg", 0.8);
  };

  const stopStream = useCallback(() => {
    clearInterval(intervalRef.current);
    if (wsRef.current) wsRef.current.close();
    if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    setStatus("stopped");
    setFaceDetected(false);
    setRoi(null);
  }, []);

  useEffect(() => () => stopStream(), [stopStream]);

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <span className="logo">◈</span>
          <h1>FaceROI</h1>
          <span className="version">v2.0</span>
        </div>
        <div className="status-pill" data-status={status}>
          <span className="dot" />
          {status === "idle"       && "Ready"}
          {status === "connecting" && "Connecting…"}
          {status === "streaming"  && `Live · ${fps} fps`}
          {status === "stopped"    && "Stopped"}
        </div>
      </header>

      <main className="main">
        <section className="feed-section">
          <div className="video-wrapper" data-detected={faceDetected}>
            <video ref={videoRef} className="video-hidden" muted playsInline />
            <canvas ref={canvasRef} className="canvas" />
            {(status === "idle" || status === "stopped") && (
              <div className="overlay-idle">
                <span className="idle-icon">◈</span>
                <p>Camera feed will appear here</p>
              </div>
            )}
            {faceDetected && <div className="badge-detected">● Face Detected</div>}
            {!faceDetected && status === "streaming" && <div className="badge-none">○ No Face</div>}
          </div>
          <div className="controls">
            {status !== "streaming" ? (
              <button className="btn btn-start" onClick={startStream}>▶ Start Stream</button>
            ) : (
              <button className="btn btn-stop" onClick={stopStream}>■ Stop</button>
            )}
          </div>
          {error && <p className="error">{error}</p>}
        </section>

        <aside className="side-panel">
          <div className="card">
            <h2 className="card-title">Current ROI</h2>
            {roi ? (
              <div className="roi-grid">
                <div className="roi-cell"><span>X</span><strong>{roi.x}px</strong></div>
                <div className="roi-cell"><span>Y</span><strong>{roi.y}px</strong></div>
                <div className="roi-cell"><span>W</span><strong>{roi.width}px</strong></div>
                <div className="roi-cell"><span>H</span><strong>{roi.height}px</strong></div>
                <div className="roi-cell full"><span>Confidence</span><strong>{(roi.confidence * 100).toFixed(1)}%</strong></div>
              </div>
            ) : (
              <p className="no-data">No face in current frame</p>
            )}
          </div>

          <div className="card">
            <h2 className="card-title">Recent Detections <span className="card-sub">(from DB)</span></h2>
            {roiHistory.length === 0 ? (
              <p className="no-data">No records yet</p>
            ) : (
              <ul className="history-list">
                {roiHistory.slice(0, 8).map((r) => (
                  <li key={r.frame_id} className="history-item" data-face={r.face_detected}>
                    <span className="hist-indicator">{r.face_detected ? "●" : "○"}</span>
                    <span className="hist-id">{r.frame_id.slice(0, 8)}…</span>
                    <span className="hist-time">{new Date(r.timestamp * 1000).toLocaleTimeString()}</span>
                    {r.roi && <span className="hist-roi">{r.roi.width}×{r.roi.height}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card card-endpoints">
            <h2 className="card-title">Endpoints</h2>
            <ul className="endpoint-list">
              <li><span className="method post">POST</span>/feed/upload</li>
              <li><span className="method get">GET</span>/feed/frame/:id</li>
              <li><span className="method get">GET</span>/roi</li>
              <li><span className="method ws">WS</span>/ws/stream</li>
            </ul>
          </div>
        </aside>
      </main>
    </div>
  );
}
