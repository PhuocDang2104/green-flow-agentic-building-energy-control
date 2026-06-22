"""GreenFlow FastAPI application."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from .routers import (actions, agent, alerts, buildings, chat, electrical, entities,
                      forecast, media, reports, simulations, states, viewer)
from .ws import manager, replay_ticker


@asynccontextmanager
async def lifespan(app: FastAPI):
    ticker = asyncio.create_task(replay_ticker())
    yield
    ticker.cancel()


settings = get_settings()

app = FastAPI(
    title="GreenFlow API",
    description="Agentic digital twin platform for energy-efficient building operations",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (buildings.router, entities.router, states.router, viewer.router,
               agent.router, actions.router, simulations.router, reports.router,
               chat.router, forecast.router, media.router, alerts.router,
               electrical.router):
    app.include_router(router, prefix="/api")

settings.storage_path.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(settings.storage_path)), name="storage")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "greenflow-api"}


@app.websocket("/ws/building/{building_id}/state")
async def building_state_ws(websocket: WebSocket, building_id: str):
    room = f"building:{building_id}"
    await manager.connect(room, websocket)
    try:
        while True:
            # keep the connection alive; clients only receive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(room, websocket)
