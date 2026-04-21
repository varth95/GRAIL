"""GRail Backend — FastAPI application entry point.

Registers all routers, applies JWT middleware globally (excluding /auth/*),
and configures CORS, error handlers, and startup/shutdown events.

Requirements: 1.6, 9.1–9.5
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.auth_middleware import JWTAuthMiddleware
from app.routers.auth_router import router as auth_router
from app.routers.recommendation_router import router as recommendation_router
from app.routers.trend_router import router as trend_router
from app.routers.user_router import router as user_router
from app.routers.vision_router import router as vision_router

# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="GRail — AI Personal Stylist",
    version="0.1.0",
    description="Backend API for the GRail AI Personal Stylist application.",
)

# ── Middleware ────────────────────────────────────────────────────────────────

# CORS — tighten origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT auth — exempts /auth/* automatically (see auth_middleware.py)
app.add_middleware(JWTAuthMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(vision_router)
app.include_router(trend_router)
app.include_router(recommendation_router)

# ── Startup / shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """Auto-create all DB tables on startup (works with SQLite, no Alembic needed)."""
    from app.db.base import Base
    from app.db.session import engine
    import app.db.orm_models  # noqa: F401 — registers all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)



@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Dispose DB engine on shutdown."""
    from app.db.session import engine
    await engine.dispose()


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"], include_in_schema=False)
async def health() -> dict:
    return {"status": "ok"}
