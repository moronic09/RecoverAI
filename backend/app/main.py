print("STARTUP: main.py module loading...", flush=True)

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from sqlalchemy import select

from app.api import auth, dashboard, simulation, transactions
from app.auth.dependencies import get_current_merchant
from app.config import get_settings
from app.database import AsyncSessionLocal, Base, engine
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.schemas import MerchantResponse
from app.services.redis_events import is_live_feed_enabled, subscribe_events
from app.tasks.simulation_tasks import generate_live_event
from app.websocket.manager import manager

settings = get_settings()


async def _redis_event_listener():
    async def forward(event: dict):
        await manager.broadcast(event)

    try:
        await subscribe_events(forward)
    except asyncio.CancelledError:
        pass


async def _live_feed_loop():
    while True:
        if is_live_feed_enabled():
            await generate_live_event()
        await asyncio.sleep(settings.live_feed_interval_seconds)


async def _seed_demo_if_needed():
    async with AsyncSessionLocal() as db:
        merchant_result = await db.execute(select(Merchant).where(Merchant.email == "demo@recoverai.com"))
        merchant = merchant_result.scalar_one_or_none()
        if merchant:
            transaction_result = await db.execute(
                select(Transaction.id).where(Transaction.merchant_id == merchant.id).limit(1)
            )
        else:
            transaction_result = None

        if transaction_result and transaction_result.scalar_one_or_none():
            print("Demo database already seeded, skipping.")
            return

    print("No existing demo data found — seeding demo database...")
    from scripts.seed_demo import seed

    await seed(transaction_limit=250)


async def _run_demo_seed():
    started_at = time.monotonic()
    print("Starting demo data seed...")
    try:
        await _seed_demo_if_needed()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"Demo data seed failed after {time.monotonic() - started_at:.2f}s: {exc}")
    else:
        print(f"Demo data seed completed in {time.monotonic() - started_at:.2f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("STARTUP: lifespan entered", flush=True)
    print("STARTUP: creating database tables...", flush=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("STARTUP: database tables ready", flush=True)

    seed_task = asyncio.create_task(_run_demo_seed())
    listener_task = asyncio.create_task(_redis_event_listener())
    live_feed_task = asyncio.create_task(_live_feed_loop())
    print("STARTUP: background tasks created, startup returning", flush=True)
    yield

    seed_task.cancel()
    listener_task.cancel()
    live_feed_task.cancel()
    try:
        await seed_task
    except asyncio.CancelledError:
        pass
    try:
        await listener_task
    except asyncio.CancelledError:
        pass
    try:
        await live_feed_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="AI-powered failed payment recovery platform",
    version="1.0.0",
    lifespan=lifespan,
)
print("STARTUP: FastAPI app created", flush=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(simulation.router, prefix="/api")


@app.get("/api/auth/me", response_model=MerchantResponse)
async def get_me(merchant: Merchant = Depends(get_current_merchant)):
    return merchant


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"event_type": "connected", "message": "Live feed connected"})
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_json({"event_type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"event_type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
