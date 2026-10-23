from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.conversations import router as conversations_router
from app.api.liara import router as liara_router
from app.api.local_fs import router as local_fs_router
from app.api.maintain import router as maintain_router
from app.api.orchestrator import router as orchestrator_router
from app.api.settings import router as settings_router
from app.config import get_settings
from app.db.session import check_db, get_session_factory
from app.services.registry import CapabilityRegistry


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Seed capability catalog when Postgres is reachable (idempotent)."""
    try:
        factory = get_session_factory()
        with factory() as session:
            inserted = CapabilityRegistry(session).seed()
            session.commit()
            if inserted:
                print(f"capability registry seeded; inserted={inserted}")
    except Exception as exc:  # noqa: BLE001 — startup must not crash on empty DB
        print(f"capability registry seed skipped: {exc}")
    yield


app = FastAPI(title="liara-companion-agent", version="0.1.0", lifespan=lifespan)

_settings = get_settings()
_origins = {_settings.web_origin, "http://localhost:3000", "http://127.0.0.1:3000"}
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_router)
app.include_router(conversations_router)
app.include_router(liara_router)
app.include_router(local_fs_router)
app.include_router(orchestrator_router)
app.include_router(maintain_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness — always ok even if DB is down (slice 02 choice)."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, object]:
    """Readiness — reports Postgres connectivity without failing the process."""
    db_ok = check_db()
    return {"status": "ready" if db_ok else "degraded", "database": db_ok}
