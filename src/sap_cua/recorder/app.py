"""SAP-CUA recorder app — web UI for recording demonstrations."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sap_cua.recorder import SAPRecorder

logger = logging.getLogger(__name__)
app = FastAPI(title="SAP-CUA Recorder")
recorder = SAPRecorder()


@app.get("/")
async def index():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html><head><title>SAP-CUA Recorder</title>
<style>
body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }
.card { border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
button { padding: 8px 16px; margin: 4px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-start { background: #28a745; color: white; }
.btn-stop { background: #dc3545; color: white; }
.btn-pause { background: #ffc107; color: black; }
.status { font-weight: bold; }
.recording { color: #dc3545; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0.5; } }
</style></head><body>
<h1>SAP-CUA Recorder</h1>
<div class="card">
  <h2>Session</h2>
  <p>Task description: <input id="task" placeholder="e.g. Create HTTPS to OData iFlow" style="width:100%;padding:8px;"></p>
  <button class="btn-start" onclick="start()">Record</button>
  <button class="btn-pause" onclick="pause()">Pause</button>
  <button class="btn-stop" onclick="stop()">Stop</button>
  <button onclick="markSuccess()">Mark Success</button>
  <button onclick="markFailure()">Mark Failure</button>
</div>
<div class="card">
  <h2>Status: <span id="status" class="status">Idle</span></h2>
  <div id="events" style="background:#f8f9fa;padding:12px;border-radius:4px;max-height:300px;overflow:auto;"></div>
</div>
<script>
let sessionId = null;
async function start() {
  const task = document.getElementById('task').value || 'Untitled task';
  const res = await fetch('/api/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({task, mode: 'human_demonstration'})
  });
  const data = await res.json();
  sessionId = data.session_id;
  document.getElementById('status').innerHTML = '<span class="recording">RECORDING</span>';
}
async function stop() {
  if (!sessionId) return;
  const res = await fetch(`/api/stop/${sessionId}`, {method: 'POST'});
  const data = await res.json();
  document.getElementById('status').textContent = 'Stopped: ' + (data.success ? 'SUCCESS' : 'FAILURE');
  sessionId = null;
}
async function pause() { await fetch('/api/pause', {method: 'POST'}); }
async function markSuccess() { await fetch('/api/mark/success', {method: 'POST'}); }
async function markFailure() { await fetch('/api/mark/failure', {method: 'POST'}); }
setInterval(async () => {
  const res = await fetch('/api/status');
  const data = await res.json();
  document.getElementById('events').textContent = JSON.stringify(data, null, 2);
}, 2000);
</script></body></html>
""")


@app.get("/api/status")
async def status():
    return JSONResponse({
        "status": recorder.session.status if recorder.session else "idle",
        "recording": recorder.session is not None and recorder.session.status == "recording",
        "mode": recorder.session.mode if recorder.session else "none",
    })


@app.post("/api/start")
async def start_recording(data: dict = {}):
    session = recorder.start(data.get("task", "Untitled"), data.get("mode", "human_demonstration"))
    return JSONResponse({
        "session_id": session.session_id,
        "status": "recording",
        "task": session.task_id,
    })


@app.post("/api/stop/{session_id}")
async def stop_recording(session_id: str):
    completed = recorder.stop()
    return JSONResponse({"session_id": completed.session_id, "success": completed.metadata.get("success")})


@app.post("/api/pause")
async def pause_recording():
    recorder.pause()
    return JSONResponse({"status": "paused"})


@app.post("/api/mark/{mark}")
async def mark_result(mark: str):
    if mark == "success":
        recorder.mark_success()
    elif mark == "failure":
        recorder.mark_failure()
    return JSONResponse({"marked": mark})


def run_recorder(port: int = 8080) -> None:
    uvicorn.run(app, host="0.0.0.0", port=port)
