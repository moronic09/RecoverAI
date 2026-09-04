from fastapi import APIRouter

from app.schemas import SimulationToggle
from app.services.redis_events import is_live_feed_enabled, set_live_feed_enabled

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/live-feed")
async def toggle_live_feed(toggle: SimulationToggle):
    set_live_feed_enabled(toggle.enabled)
    return {"enabled": toggle.enabled, "message": f"Live feed {'enabled' if toggle.enabled else 'disabled'}"}


@router.get("/live-feed/status")
async def live_feed_status():
    return {"enabled": is_live_feed_enabled()}
