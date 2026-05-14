from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/progress/{project_id}")
async def ws_progress(websocket: WebSocket, project_id: int):
    """WebSocket для получения обновлений прогресса в реальном времени."""
    await websocket.accept()
    try:
        await websocket.send_json({"type": "connected", "project_id": project_id, "detail": "WebSocket заглушка"})
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "echo", "received": data})
    except WebSocketDisconnect:
        pass


@router.websocket("/alerts/{project_id}")
async def ws_alerts(websocket: WebSocket, project_id: int):
    """WebSocket для получения оповещений по проекту."""
    await websocket.accept()
    try:
        await websocket.send_json({"type": "connected", "project_id": project_id, "detail": "Канал оповещений — заглушка"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
